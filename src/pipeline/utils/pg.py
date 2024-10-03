import os
from typing import Iterable, List, Type

from sqlalchemy import UUID, create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.orm.session import Session
from src.pipeline.models import (
    DependsOn,
    License,
    LoadHistory,
    Package,
    PackageManager,
    PackageURL,
    URLType,
    User,
    URL,
    Version,
)
from src.pipeline.utils.logger import Logger

CHAI_DATABASE_URL = os.getenv("CHAI_DATABASE_URL")


# ORMs suck, go back to SQL
class DB:
    def __init__(self):
        self.logger = Logger("DB")
        self.engine = create_engine(CHAI_DATABASE_URL)
        self.session = sessionmaker(self.engine)
        self.logger.debug("connected")

    # TODO: the database client should not handle batching
    # we should move this to the transformer
    def _batch(
        self,
        items: Iterable[DeclarativeMeta],
        model: Type[DeclarativeMeta],
        batch_size: int = 10000,
    ) -> None:
        """just handles batching logic for any type of model we wanna insert"""
        self.logger.debug("starting a batch insert")
        with self.session() as session:
            batch = []
            for item in items:
                batch.append(item)
                if len(batch) == batch_size:
                    self.logger.debug(f"inserting {len(batch)} {model.__name__}")
                    self._insert_batch(batch, session, model)
                    batch = []  # reset

            if batch:
                self.logger.debug(f"finally, inserting {len(batch)} {model.__name__}")
                self._insert_batch(batch, session, model)

            session.commit()  # commit here

    def _insert_batch(
        self,
        batch: List[DeclarativeMeta],
        session: Session,
        model: Type[DeclarativeMeta],
    ) -> None:
        """
        inserts a batch of items, any model, into the database
        however, this mandates `on conflict do nothing`
        """
        # we use statements here, not the ORM because of the on_conflict_do_nothing
        # https://github.com/sqlalchemy/sqlalchemy/issues/5374
        stmt = (
            insert(model)
            .values([item.to_dict() for item in batch])
            .on_conflict_do_nothing()
        )
        session.execute(stmt)

    # TODO: inefficient insertion processes
    # the following functions are all about insertions
    # since we store `import_ids` in the db, we query the db for every single
    # insertion, which is not ideal
    # since we're removing ORMs completely, we should be able to batch
    # these queries as well

    def insert_packages(
        self, package_generator: Iterable[str], package_manager: PackageManager
    ) -> List[UUID]:
        def package_object_generator():
            for item in package_generator:
                name = item["name"]
                import_id = item["import_id"]
                readme = item["readme"]
                yield Package(
                    derived_id=f"{package_manager.name}/{name}",
                    name=name,
                    package_manager_id=package_manager.id,
                    import_id=import_id,
                    readme=readme,
                )

        return self._batch(package_object_generator(), Package)

    def insert_versions(self, version_generator: Iterable[dict[str, str]]):
        def version_object_generator():
            for item in version_generator:
                crate_id = item["crate_id"]
                version = item["version"]
                import_id = item["import_id"]
                size = item["size"]
                published_at = item["published_at"]
                license_name = item["license"]
                downloads = item["downloads"]
                checksum = item["checksum"]

                # the crate_id is a Package.import_id
                package = self.select_package_by_import_id(crate_id)
                if package is None:
                    self.logger.warn(f"package with import_id {crate_id} not found")
                    continue
                package_id = package.id

                # similarly, for license_id
                license_id = self.select_license_by_name(license_name, create=True)

                yield Version(
                    package_id=package_id,
                    version=version,
                    import_id=import_id,
                    size=size,
                    published_at=published_at,
                    license_id=license_id,
                    downloads=downloads,
                    checksum=checksum,
                )

        self._batch(version_object_generator(), Version)

    def insert_dependencies(self, dependency_generator: Iterable[dict[str, str]]):
        def dependency_object_generator():
            for item in dependency_generator:
                start_id = item["start_id"]
                end_id = item["end_id"]
                semver_range = item["semver_range"]
                dependency_type = item["dependency_type"]

                version = self.select_version_by_import_id(start_id)
                if version is None:
                    self.logger.warn(f"version with import_id {start_id} not found")
                    continue
                version_id = version.id

                dependency = self.select_package_by_import_id(end_id)
                if dependency is None:
                    self.logger.warn(f"package with import_id {end_id} not found")
                    continue
                dependency_id = dependency.id

                yield DependsOn(
                    version_id=version_id,
                    dependency_id=dependency_id,
                    semver_range=semver_range,
                    # dependency_type=dependency_type, TODO: add this
                )

        self._batch(dependency_object_generator(), DependsOn, 10000)

    def insert_load_history(self, package_manager_id: str):
        with self.session() as session:
            session.add(LoadHistory(package_manager_id=package_manager_id))
            session.commit()

    def insert_package_manager(self, package_manager: str) -> UUID | None:
        with self.session() as session:
            exists = self.select_package_manager_id(package_manager) is not None
            if not exists:
                session.add(PackageManager(name=package_manager))
                session.commit()
                return (
                    session.query(PackageManager)
                    .filter_by(name=package_manager)
                    .first()
                    .id
                )

    def insert_url_types(self, name: str) -> UUID:
        with self.session() as session:
            session.add(URLType(name=name))
            session.commit()
            return session.query(URLType).filter_by(name=name).first().id

    def insert_users(self, user_generator: Iterable[dict[str, str]]):
        def user_object_generator():
            for item in user_generator:
                username = item["username"]
                yield User(username=username)

        self._batch(user_object_generator(), User, 10000)

    def insert_urls(self, url_generator: Iterable[str]):
        def url_object_generator():
            for item in url_generator:
                yield URL(url=item)

        self._batch(url_object_generator(), URL, 10000)

    def insert_package_urls(self, package_url_generator: Iterable[dict[str, str]]):
        def package_url_object_generator():
            for item in package_url_generator:
                yield PackageURL(
                    package_id=item["package_id"],
                    url_id=item["url_id"],
                    url_type_id=item["url_type_id"],
                )

        self._batch(package_url_object_generator(), PackageURL)

    def print_statement(self, stmt):
        dialect = postgresql.dialect()
        compiled_stmt = stmt.compile(
            dialect=dialect, compile_kwargs={"literal_binds": True}
        )
        self.logger.log(str(compiled_stmt))

    def select_url_types_homepages(self) -> List[URLType]:
        with self.session() as session:
            result = session.query(URLType).filter_by(name="homepage").first()
            if result:
                return result.id

    def select_url_types_repositories(self) -> List[URLType]:
        with self.session() as session:
            result = session.query(URLType).filter_by(name="repository").first()
            if result:
                return result.id

    def select_package_manager_id(
        self, package_manager: str, create: bool = False
    ) -> UUID | None:
        with self.session() as session:
            result = (
                session.query(PackageManager).filter_by(name=package_manager).first()
            )

            if result:
                self.logger.debug(f"id: {result.id}")
                return result.id
            if create:
                session.add(PackageManager(name=package_manager))
                session.commit()
                return (
                    session.query(PackageManager)
                    .filter_by(name=package_manager)
                    .first()
                    .id
                )
            return None

    def select_package_by_import_id(self, import_id: str) -> Package | None:
        with self.session() as session:
            result = session.query(Package).filter_by(import_id=import_id).first()
            if result:
                return result

    def select_license_by_name(
        self, license_name: str, create: bool = False
    ) -> UUID | None:
        with self.session() as session:
            result = session.query(License).filter_by(name=license_name).first()
            if result:
                return result.id
            if create:
                session.add(License(name=license_name))
                session.commit()
                return session.query(License).filter_by(name=license_name).first().id
            return None

    def select_version_by_import_id(self, import_id: str) -> Version | None:
        with self.session() as session:
            result = session.query(Version).filter_by(import_id=import_id).first()
            if result:
                return result


if __name__ == "__main__":
    db = DB()
    # random tests
