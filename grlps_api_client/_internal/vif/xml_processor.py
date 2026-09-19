"""
VIF XML to JSON: parse Vendor Info File XML into HAR/API payload shape.
Used for PutVIFData/PortA and verification. Same shape as HAR-recorded payloads.
"""
import re
import xml.etree.ElementTree as ET


class XMLProcessor:
    def _normalize_pdo_decoded_value(self, text_value):
        """
        PDO decoded values in HAR are typically numeric strings (without units/factor suffix).
        Example: "5000 mV (Factor = 50)" -> "5000"
        """
        if not text_value:
            return text_value
        if "%" in text_value:
            return text_value
        match = re.search(r"-?\d+(?:\.\d+)?", text_value)
        if match:
            return match.group(0)
        return text_value

    def __init__(self, xml_file):
        self.xml_file = xml_file
        self.namespaces = {"vif": "http://usb.org/VendorInfoFile.xsd"}
        self.tree = ET.parse(xml_file)
        self.root = self.tree.getroot()

    def convert_value(self, value):
        if value.lower() in ["true", "false"]:
            return 1 if value.lower() == "true" else 0
        try:
            return int(value)
        except ValueError:
            return value

    def convert_decoded_value(self, element, tag):
        if "value" in element.attrib:
            value = element.attrib["value"].lower()
            if value == "true":
                return "YES"
            elif value == "false":
                return "NO"

        text_value = element.text.strip() if element.text else ""

        if "%" in text_value:
            return text_value
        return text_value

    def process_subfields(self, subfield_list):
        processed_subfields = []
        grouped_modes = []
        for subfield in subfield_list:
            nested_fields = []
            for field in subfield:
                tag_name = field.tag.split("}")[1]
                # Skip container nodes; only keep leaf field entries.
                if tag_name.endswith("List"):
                    continue
                node = {
                    "enum": tag_name,
                    "decodedValue": self.convert_decoded_value(field, field.tag),
                }
                if "value" in field.attrib:
                    node["specValue"] = self.convert_value(field.attrib.get("value", ""))
                nested_fields.append(node)

            grouped_modes.append(
                {
                    "vifFieldList": nested_fields,
                    "vifSubFieldList": self.process_subfields(
                        subfield.findall(
                            "vif:SOPSVIDModeList/vif:SOPSVIDMode",
                            self.namespaces,
                        )
                    ),
                }
            )
        if grouped_modes:
            processed_subfields.append({"vifFieldList": [], "vifSubFieldList": grouped_modes})
        return processed_subfields

    def _pdo_field_units(self, tag, decoded_value):
        """Units for PDO fields (source and sink). Align with C# VIFElementType / HAR."""
        if "Voltage" in tag or "Min_Voltage" in tag or "Max_Voltage" in tag:
            return "mV"
        if "Current" in tag:
            return "mA"
        if "Power" in tag or "Op_Power" in tag:
            return "mW"
        if "Debounce" in tag:
            return "msec"
        if "Threshold" in tag:
            return "mA"
        return None

    def _extract_pdo_list(self, pdo_list):
        """Extract PDO list (source or sink) to dict "1", "2", ... with vifFieldList/vifSubFieldList. Handles different PDO types (Fixed, Battery, etc.)."""
        result = {}
        for idx, pdo in enumerate(pdo_list, start=1):
            pdo_fields = []
            for child in pdo:
                tag = child.tag.split("}")[1]
                decoded_value = self._normalize_pdo_decoded_value(
                    self.convert_decoded_value(child, tag)
                )
                field = {
                    "enum": tag,
                    "decodedValue": decoded_value,
                }
                if "value" in child.attrib:
                    field["specValue"] = self.convert_value(child.attrib.get("value", ""))
                units = self._pdo_field_units(tag, decoded_value)
                if units:
                    field["units"] = units
                if decoded_value and ("%" in decoded_value or "Percentage" in decoded_value):
                    field.pop("units", None)
                pdo_fields.append(field)
            result[str(idx)] = {
                "vifFieldList": pdo_fields,
                "vifSubFieldList": [],
            }
        return result

    def extract_non_component_vif_elements(self):
        non_component_vif_elements = []
        tags_to_extract = [
            "VIF_Specification",
            "Vendor_Name",
            "Model_Part_Number",
            "Product_Revision",
            "TID",
            "VIF_Product_Type",
            "Certification_Type",
        ]
        for tag in tags_to_extract:
            element = self.root.find(f"vif:{tag}", self.namespaces)
            if element is not None:
                non_component_vif_elements.append(
                    {
                        "enum": tag,
                        "specValue": self.convert_value(element.attrib.get("value", "")),
                        "decodedValue": self.convert_decoded_value(element, tag),
                    }
                )
        return non_component_vif_elements

    def _element_to_field(self, element, tag):
        """Build one VIF element dict (enum, specValue, decodedValue, optional units)."""
        decoded = self.convert_decoded_value(element, tag)
        field = {
            "enum": tag,
            "decodedValue": decoded,
        }
        if "value" in element.attrib:
            field["specValue"] = self.convert_value(element.attrib.get("value", ""))
        # HAR commonly stores PD power-as-source/sink decoded values as plain numbers.
        if "PD_Power_As_" in tag:
            field["decodedValue"] = self._normalize_pdo_decoded_value(decoded)
            field["units"] = "mW"
        return field

    def extract_static_product_fields(self):
        """All Product-level static fields (exclude USB4RouterList; that is in USB4Routers). Align with HAR/C#."""
        static_product_fields = []
        product_section = self.root.find("vif:Product", self.namespaces)
        if product_section is None:
            return static_product_fields
        skip_tags = {"USB4RouterList", "Usb4Router"}
        for child in product_section:
            tag = child.tag.split("}")[1]
            if tag in skip_tags:
                continue
            static_product_fields.append(self._element_to_field(child, tag))
        return static_product_fields

    def extract_usb4_routers(self):
        """Build USB4Routers dict from Product/USB4RouterList/Usb4Router. Keys "1", "2", ... with vifFieldList/vifSubFieldList."""
        routers = {}
        product_section = self.root.find("vif:Product", self.namespaces)
        if product_section is None:
            return routers
        router_list = product_section.find("vif:USB4RouterList", self.namespaces)
        if router_list is None:
            return routers
        for idx, router in enumerate(router_list.findall("vif:Usb4Router", self.namespaces), start=1):
            fields = []
            for child in router:
                tag = child.tag.split("}")[1]
                fields.append(self._element_to_field(child, tag))
            routers[str(idx)] = {"vifFieldList": fields, "vifSubFieldList": []}
        return routers

    COMPONENT_SKIP_TAGS = frozenset(["SrcPdoList", "SnkPdoList", "SOPSVIDList", "CableSVIDList"])

    def _extract_svid_dict(self, svid_list):
        """Build SVID dict from list of SOPSVID or CableSVID elements. Keys "1", "2", ..."""
        result = {}
        for idx, svid in enumerate(svid_list, start=1):
            svid_fields = []
            for svid_field in svid:
                if "ModeList" not in svid_field.tag:
                    tag = svid_field.tag.split("}")[1]
                    svid_fields.append(self._element_to_field(svid_field, tag))
            cable_subfields = svid.findall("vif:CableSVIDModeList/vif:CableSVIDMode", self.namespaces)
            sop_subfields = svid.findall("vif:SOPSVIDModeList/vif:SOPSVIDMode", self.namespaces)
            subfields = cable_subfields if cable_subfields else sop_subfields
            result[str(idx)] = {
                "vifFieldList": svid_fields,
                "vifSubFieldList": self.process_subfields(subfields),
            }
        return result

    def extract_components(self):
        """All components: staticPortElements (all port fields), sourcePDOs, sinkPDOs, sVIDs, cableSVIDs, OptionalContent. Handles different source/sink PDO counts and types."""
        components = self.root.findall("vif:Component", self.namespaces)
        vif_components = []
        for component in components:
            static_port_elements = []
            for child in component:
                tag = child.tag.split("}")[1]
                if tag in self.COMPONENT_SKIP_TAGS:
                    continue
                static_port_elements.append(self._element_to_field(child, tag))

            src_pdo_list = component.findall("vif:SrcPdoList/vif:SrcPDO", self.namespaces)
            sink_pdo_list = component.findall("vif:SnkPdoList/vif:SnkPDO", self.namespaces)

            sopsvid_list = component.findall("vif:SOPSVIDList/vif:SOPSVID", self.namespaces)
            cablesvid_list = component.findall("vif:CableSVIDList/vif:CableSVID", self.namespaces)
            sVIDs = self._extract_svid_dict(sopsvid_list)
            cableSVIDs = self._extract_svid_dict(cablesvid_list)

            vif_components.append(
                {
                    "staticPortElements": static_port_elements,
                    "sourcePDOs": self._extract_pdo_list(src_pdo_list),
                    "sinkPDOs": self._extract_pdo_list(sink_pdo_list),
                    "sVIDs": sVIDs,
                    "cableSVIDs": cableSVIDs,
                    "OptionalContent": {
                        "DisplayPort_Product_Summary": {},
                        "SOP_DP_Capabilities": {},
                        "SOPP_DisplayPort_Capabilities": {},
                        "DisplayPort_Status": {},
                        "VIF_App": {},
                    },
                }
            )
        return vif_components

    def process_xml(self):
        """Build VIF payload for PutVIFData/PortA. Same shape as HAR: nonComponentVIFElements, vifproductFields (staticProductFields + USB4Routers), vifComponents."""
        non_component_vif_elements = self.extract_non_component_vif_elements()
        static_product_fields = self.extract_static_product_fields()
        usb4_routers = self.extract_usb4_routers()
        vif_components = self.extract_components()
        final_data = {
            "nonComponentVIFElements": non_component_vif_elements,
            "vifproductFields": [{"staticProductFields": static_product_fields, "USB4Routers": usb4_routers}],
            "vifComponents": vif_components,
        }
        return final_data

