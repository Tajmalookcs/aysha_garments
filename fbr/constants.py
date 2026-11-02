"""FBR facts, all from PRAL's Technical Specification for DI API v1.12 in reference/."""

POST_SANDBOX = "/di_data/v1/di/postinvoicedata_sb"
VALIDATE_SANDBOX = "/di_data/v1/di/validateinvoicedata_sb"

# Lists downloaded whole: name, path, value key.
REFERENCE_LISTS = {
    "provinces": ("/pdi/v1/provinces", "stateProvinceDesc"),
    "uom": ("/pdi/v1/uom", "description"),
    "hs_codes": ("/pdi/v1/itemdesccode", "hS_CODE"),
    "transaction_types": ("/pdi/v1/transtypecode", "transactioN_DESC"),
    "document_types": ("/pdi/v1/doctypecode", "docDescription"),
    "sro_items": ("/pdi/v1/sroitemcode", "srO_ITEM_DESC"),
}
SALE_TYPE_TO_RATE = "/pdi/v2/SaleTypeToRate"

# Spec section 9: code, description, sale type.
SCENARIOS = {
    "SN001": ("Goods at standard rate to registered buyers", "Goods at Standard Rate (default)"),
    "SN002": ("Goods at standard rate to unregistered buyers", "Goods at Standard Rate (default)"),
    "SN003": ("Sale of Steel (Melted and Re-Rolled)", "Steel Melting and re-rolling"),
    "SN004": ("Sale by Ship Breakers", "Ship breaking"),
    "SN005": ("Reduced rate sale", "Goods at Reduced Rate"),
    "SN006": ("Exempt goods sale", "Exempt Goods"),
    "SN007": ("Zero rated sale", "Goods at zero-rate"),
    "SN008": ("Sale of 3rd schedule goods", "3rd Schedule Goods"),
    "SN009": ("Cotton Spinners purchase from Cotton Ginners (Textile Sector)", "Cotton Ginners"),
    "SN010": ("Telecom services rendered or provided", "Telecommunication services"),
    "SN011": ("Toll Manufacturing sale by Steel sector", "Toll Manufacturing"),
    "SN012": ("Sale of Petroleum products", "Petroleum Products"),
    "SN013": ("Electricity Supply to Retailers", "Electricity Supply to Retailers"),
    "SN014": ("Sale of Gas to CNG stations", "Gas to CNG stations"),
    "SN015": ("Sale of mobile phones", "Mobile Phones"),
    "SN016": ("Processing / Conversion of Goods", "Processing/ Conversion of Goods"),
    "SN017": ("Sale of Goods where FED is charged in ST mode", "Goods (FED in ST Mode)"),
    "SN018": ("Services rendered or provided where FED is charged in ST mode", "Services (FED in ST Mode)"),
    "SN019": ("Services rendered or provided", "Services"),
    "SN020": ("Sale of Electric Vehicles", "Electric Vehicle"),
    "SN021": ("Sale of Cement /Concrete Block", "Cement /Concrete Block"),
    "SN022": ("Sale of Potassium Chlorate", "Potassium Chlorate"),
    "SN023": ("Sale of CNG", "CNG Sales"),
    "SN024": ("Goods sold that are listed in SRO 297(1)/2023", "Goods as per SRO.297(|)/2023"),
    "SN025": ("Drugs sold at fixed ST rate under serial 81 of Eighth Schedule Table 1", "Non-Adjustable Supplies"),
    "SN026": ("Sale to End Consumer by retailers", "Goods at Standard Rate (default)"),
    "SN027": ("Sale to End Consumer by retailers", "3rd Schedule Goods"),
    "SN028": ("Sale to End Consumer by retailers", "Goods at Reduced Rate"),
}

# Plain help for common errors. FBR's own message is always shown as well.
ERROR_HELP = {
    "0002": "Check the buyer's NTN or CNIC under Customers.",
    "0005": "The invoice date format was refused.",
    "0008": "Sales tax withheld must be zero or equal to the sales tax.",
    "0012": "The buyer's registration type is missing.",
    "0046": "This product's rate doesn't match its sale type. Open the product and fix it.",
    "0052": "This product's HS code doesn't match its sale type. Open the product and fix it.",
    "0053": "The buyer's registration type isn't valid.",
    "0058": "The buyer and seller can't have the same registration number.",
    "0079": "A 5% rate isn't allowed when the value is above 20,000.",
    "0401": "FBR doesn't accept this token for the seller's NTN or CNIC. Check the company's NTN and the token.",
    "0402": "FBR doesn't accept the buyer's NTN or CNIC. Check it under Customers.",
}
