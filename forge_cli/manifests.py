import plistlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class PlistBuilder:
    """AST-based Plist builder using python's built-in plistlib."""

    def __init__(
        self, app_name: str, safe_name: str, version: str = "1.0", bundle_id: str | None = None
    ):
        self.data: dict[str, Any] = {
            "CFBundleExecutable": safe_name,
            "CFBundleIdentifier": bundle_id or f"com.forge.{safe_name}",
            "CFBundleName": app_name,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": version,
        }

    def set(self, key: str, value: Any) -> PlistBuilder:
        self.data[key] = value
        return self

    def write(self, path: Path) -> None:
        with open(path, "wb") as fp:
            plistlib.dump(self.data, fp)


class WixBuilder:
    """AST-based WiX (.wxs) builder using ElementTree."""

    def __init__(
        self,
        app_name: str,
        safe_name: str,
        dist_dir: Path,
        version: str = "1.0.0.0",
        upgrade_code: str = "PUT-GUID-HERE",
    ):
        self.app_name = app_name
        self.safe_name = safe_name
        self.dist_dir = dist_dir
        self.version = version
        self.upgrade_code = upgrade_code

        # Start AST
        ET.register_namespace("", "http://schemas.microsoft.com/wix/2006/wi")
        self.root = ET.Element("{http://schemas.microsoft.com/wix/2006/wi}Wix")

        self.product = ET.SubElement(
            self.root,
            "{http://schemas.microsoft.com/wix/2006/wi}Product",
            {
                "Id": "*",
                "Name": app_name,
                "Language": "1033",
                "Version": version,
                "Manufacturer": "Forge",
                "UpgradeCode": upgrade_code,
            },
        )

        ET.SubElement(
            self.product,
            "{http://schemas.microsoft.com/wix/2006/wi}Package",
            {"InstallerVersion": "200", "Compressed": "yes", "InstallScope": "perMachine"},
        )

        ET.SubElement(
            self.product,
            "{http://schemas.microsoft.com/wix/2006/wi}MajorUpgrade",
            {"DowngradeErrorMessage": "A newer version of [ProductName] is already installed."},
        )

        ET.SubElement(
            self.product,
            "{http://schemas.microsoft.com/wix/2006/wi}MediaTemplate",
            {"EmbedCab": "yes"},
        )

        feature = ET.SubElement(
            self.product,
            "{http://schemas.microsoft.com/wix/2006/wi}Feature",
            {"Id": "ProductFeature", "Title": app_name, "Level": "1"},
        )
        ET.SubElement(
            feature,
            "{http://schemas.microsoft.com/wix/2006/wi}ComponentGroupRef",
            {"Id": "ProductComponents"},
        )

    def build_directories(self) -> None:
        frag_dir = ET.SubElement(self.root, "{http://schemas.microsoft.com/wix/2006/wi}Fragment")
        target_dir = ET.SubElement(
            frag_dir,
            "{http://schemas.microsoft.com/wix/2006/wi}Directory",
            {"Id": "TARGETDIR", "Name": "SourceDir"},
        )
        pf_dir = ET.SubElement(
            target_dir,
            "{http://schemas.microsoft.com/wix/2006/wi}Directory",
            {"Id": "ProgramFilesFolder"},
        )
        ET.SubElement(
            pf_dir,
            "{http://schemas.microsoft.com/wix/2006/wi}Directory",
            {"Id": "INSTALLFOLDER", "Name": self.app_name},
        )

    def build_components(self) -> None:
        frag_comp = ET.SubElement(self.root, "{http://schemas.microsoft.com/wix/2006/wi}Fragment")
        comp_group = ET.SubElement(
            frag_comp,
            "{http://schemas.microsoft.com/wix/2006/wi}ComponentGroup",
            {"Id": "ProductComponents", "Directory": "INSTALLFOLDER"},
        )

        comp = ET.SubElement(
            comp_group,
            "{http://schemas.microsoft.com/wix/2006/wi}Component",
            {"Id": "MainExecutable", "Guid": "*"},
        )
        exe_path = str(self.dist_dir / f"{self.safe_name}.exe")
        ET.SubElement(
            comp,
            "{http://schemas.microsoft.com/wix/2006/wi}File",
            {"Id": "ExeFile", "Source": exe_path, "KeyPath": "yes"},
        )

    def write(self, path: Path) -> None:
        self.build_directories()
        self.build_components()
        tree = ET.ElementTree(self.root)
        # Using xml_declaration=True to add the <?xml ...?> header
        tree.write(path, encoding="utf-8", xml_declaration=True)


class AndroidManifestBuilder:
    """AST-based AndroidManifest.xml builder."""

    def __init__(
        self, app_name: str, package_name: str, version_code: str = "1", version_name: str = "1.0"
    ):
        self.app_name = app_name
        self.package_name = package_name

        self.root = ET.Element(
            "manifest",
            {
                "xmlns:android": "http://schemas.android.com/apk/res/android",
                "package": package_name,
                "android:versionCode": version_code,
                "android:versionName": version_name,
            },
        )

        self.application = ET.SubElement(
            self.root,
            "application",
            {
                "android:label": app_name,
                "android:icon": "@mipmap/ic_launcher",
                "android:theme": "@style/AppTheme",
            },
        )

        self.activity = ET.SubElement(
            self.application,
            "activity",
            {"android:name": ".MainActivity", "android:exported": "true"},
        )

        intent_filter = ET.SubElement(self.activity, "intent-filter")
        ET.SubElement(intent_filter, "action", {"android:name": "android.intent.action.MAIN"})
        ET.SubElement(
            intent_filter, "category", {"android:name": "android.intent.category.LAUNCHER"}
        )

    def write(self, path: Path) -> None:
        tree = ET.ElementTree(self.root)
        tree.write(path, encoding="utf-8", xml_declaration=True)
