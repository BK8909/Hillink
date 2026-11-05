"""Read-only XLSX text intake using ZIP/XML; no formula execution or source writes.

Used when the spreadsheet artifact runtime is unavailable. Private rows are never
automatically exported into a repository. Not a general Excel calculation engine.
"""
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def read_workbook(path):
    with ZipFile(Path(path)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 100_000_000:
            raise ValueError("workbook_uncompressed_size_limit")
        names = set(archive.namelist())
        strings = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(node.itertext()) for node in root.findall("m:si", NS)]
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        result = []
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            target = targets[sheet.attrib[REL]]
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            rows = []
            for row in ET.fromstring(archive.read(target)).findall("m:sheetData/m:row", NS):
                cells = {}
                for cell in row.findall("m:c", NS):
                    address = cell.attrib["r"]
                    kind = cell.attrib.get("t")
                    raw = cell.findtext("m:v", default="", namespaces=NS)
                    if kind == "s":
                        value = strings[int(raw)] if raw else ""
                    elif kind == "inlineStr":
                        value = "".join(cell.find("m:is", NS).itertext())
                    else:
                        value = raw
                    cells[address] = {"value": value, "formula_present": cell.find("m:f", NS) is not None}
                rows.append({"excel_row": int(row.attrib["r"]), "cells": cells})
            result.append({"sheet_name": sheet.attrib["name"], "rows": rows})
        return result


def structure_only(path):
    result = []
    for sheet in read_workbook(path):
        first = sheet["rows"][0] if sheet["rows"] else {"cells": {}}
        result.append({"sheet_name": sheet["sheet_name"], "row_count": len(sheet["rows"]),
                       "headers": {key: value["value"] for key, value in first["cells"].items()},
                       "formula_cells": sum(cell["formula_present"] for row in sheet["rows"] for cell in row["cells"].values())})
    return result
