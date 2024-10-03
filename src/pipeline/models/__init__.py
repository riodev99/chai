# __init__.py
from __future__ import annotations
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    func,
)

# from sqlalchemy.orm import Mapped
# from sqlalchemy.orm import mapped_column
# from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base


naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=naming_convention)
Base = declarative_base(metadata=metadata)


class Package(Base):
    __tablename__ = "packages"
    __table_args__ = (
        UniqueConstraint(
            "package_manager_id", "import_id", name="uq_package_manager_import_id"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    derived_id = Column(String, nullable=False, unique=True)  # package_manager/name
    name = Column(String, nullable=False, index=True)
    package_manager_id = Column(
        UUID(as_uuid=True), ForeignKey("package_managers.id"), nullable=False
    )
    # the import_id is from our data source (e.g., crate_id)
    # it is non-nullable, and we'll default to name if not provided by source
    import_id = Column(String, nullable=False, index=True)
    readme = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())

    def to_dict(self):
        return {
            "derived_id": self.derived_id,
            "name": self.name,
            "package_manager_id": self.package_manager_id,
            "import_id": self.import_id,
            "readme": self.readme,
        }


class PackageManager(Base):
    __tablename__ = "package_managers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())


# this is a collection of all the different type of URLs
class URL(Base):
    __tablename__ = "urls"
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    url = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())

    def to_dict(self):
        return {"url": self.url}


class URLType(Base):
    __tablename__ = "url_types"
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    name = Column(String, nullable=False, unique=True)  # repo, homepage, etc
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (
        UniqueConstraint("package_id", "version", name="uq_package_version"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False)
    version = Column(String, nullable=False, index=True)
    import_id = Column(String, nullable=False, index=True)
    # size, published_at, license_id, downloads, checksum
    # are nullable bc not all sources provide them
    size = Column(Integer, nullable=True, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    license_id = Column(UUID(as_uuid=True), ForeignKey("licenses.id"), nullable=True)
    downloads = Column(Integer, nullable=True, index=True)
    checksum = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())

    # package: Mapped["Package"] = relationship()
    # license: Mapped["License"] = relationship()

    def to_dict(self):
        return {
            "package_id": self.package_id,
            "version": self.version,
            "import_id": self.import_id,
            "size": self.size,
            "published_at": self.published_at,
            "license_id": self.license_id,
            "downloads": self.downloads,
            "checksum": self.checksum,
        }


class License(Base):
    __tablename__ = "licenses"
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())


class DependsOn(Base):
    __tablename__ = "dependencies"
    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "dependency_id",
            "dependency_type",
            name="uq_version_dependency_type",
        ),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    version_id = Column(UUID(as_uuid=True), ForeignKey("versions.id"), nullable=False)
    dependency_id = Column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False
    )
    # ideally, these are non-nullable but diff package managers are picky about this
    dependency_type = Column(String, nullable=True)
    semver_range = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def to_dict(self):
        return {
            "version_id": self.version_id,
            "dependency_id": self.dependency_id,
            "dependency_type": self.dependency_type,
            "semver_range": self.semver_range,
        }


class LoadHistory(Base):
    __tablename__ = "load_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    package_manager_id = Column(
        UUID(as_uuid=True), ForeignKey("package_managers.id"), nullable=False
    )
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())


class PackageURL(Base):
    __tablename__ = "package_urls"
    __table_args__ = (
        UniqueConstraint(
            "package_id", "url_id", "url_type_id", name="uq_package_url_type"
        ),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False)
    url_id = Column(UUID(as_uuid=True), ForeignKey("urls.id"), nullable=False)
    url_type_id = Column(UUID(as_uuid=True), ForeignKey("url_types.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())

    def to_dict(self):
        return {
            "package_id": self.package_id,
            "url_id": self.url_id,
            "url_type_id": self.url_type_id,
        }


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    username = Column(String, nullable=False, unique=True)
    import_id = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())

    def to_dict(self):
        return {"username": self.username}


class UserType(Base):
    __tablename__ = "user_types"
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    name = Column(String, nullable=False, unique=True)  # github, gitlab, crates, etc.
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())


class UserURL(Base):
    __tablename__ = "user_urls"
    __table_args__ = (
        UniqueConstraint("user_id", "url_id", "user_type_id", name="uq_user_url_type"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    url_id = Column(UUID(as_uuid=True), ForeignKey("urls.id"), nullable=False)
    user_type_id = Column(
        UUID(as_uuid=True), ForeignKey("user_types.id"), nullable=False
    )
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())


class UserVersion(Base):
    __tablename__ = "user_versions"
    __table_args__ = (
        UniqueConstraint("user_id", "version_id", name="uq_user_version"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    version_id = Column(UUID(as_uuid=True), ForeignKey("versions.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())


class UserPackage(Base):
    __tablename__ = "user_packages"
    __table_args__ = (
        UniqueConstraint("user_id", "package_id", name="uq_user_package"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())
