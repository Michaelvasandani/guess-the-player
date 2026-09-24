"""Transfermarkt country name -> (ISO 3166 alpha-2 / flag code, continent)."""

EU, AF, AS, NA, SA, OC = "Europe", "Africa", "Asia", "North America", "South America", "Oceania"

COUNTRIES = {
    "Afghanistan": ("AF", AS), "Albania": ("AL", EU), "Algeria": ("DZ", AF), "Andorra": ("AD", EU),
    "Angola": ("AO", AF), "Antigua and Barbuda": ("AG", NA), "Argentina": ("AR", SA), "Armenia": ("AM", EU),
    "Aruba": ("AW", NA), "Australia": ("AU", OC), "Austria": ("AT", EU), "Azerbaijan": ("AZ", EU),
    "Bahrain": ("BH", AS), "Bangladesh": ("BD", AS), "Barbados": ("BB", NA), "Belarus": ("BY", EU),
    "Belgium": ("BE", EU), "Belize": ("BZ", NA), "Benin": ("BJ", AF), "Bermuda": ("BM", NA),
    "Bhutan": ("BT", AS), "Bolivia": ("BO", SA), "Bonaire": ("BQ", NA), "Bosnia-Herzegovina": ("BA", EU),
    "Botswana": ("BW", AF), "Brazil": ("BR", SA), "Brunei Darussalam": ("BN", AS), "Bulgaria": ("BG", EU),
    "Burkina Faso": ("BF", AF), "Burundi": ("BI", AF), "Cambodia": ("KH", AS), "Cameroon": ("CM", AF),
    "Canada": ("CA", NA), "Cape Verde": ("CV", AF), "Central African Republic": ("CF", AF), "Chad": ("TD", AF),
    "Chile": ("CL", SA), "China": ("CN", AS), "Chinese Taipei": ("TW", AS), "Colombia": ("CO", SA),
    "Comoros": ("KM", AF), "Congo": ("CG", AF), "Costa Rica": ("CR", NA), "Cote d'Ivoire": ("CI", AF),
    "Croatia": ("HR", EU), "Cuba": ("CU", NA), "Curacao": ("CW", NA), "Cyprus": ("CY", EU),
    "Czech Republic": ("CZ", EU), "DR Congo": ("CD", AF), "Denmark": ("DK", EU), "Dominican Republic": ("DO", NA),
    "Ecuador": ("EC", SA), "Egypt": ("EG", AF), "El Salvador": ("SV", NA), "England": ("GB-ENG", EU),
    "Equatorial Guinea": ("GQ", AF), "Eritrea": ("ER", AF), "Estonia": ("EE", EU), "Ethiopia": ("ET", AF),
    "Faroe Islands": ("FO", EU), "Fiji": ("FJ", OC), "Finland": ("FI", EU), "France": ("FR", EU),
    "French Guiana": ("GF", SA), "Gabon": ("GA", AF), "Georgia": ("GE", EU), "Germany": ("DE", EU),
    "Ghana": ("GH", AF), "Gibraltar": ("GI", EU), "Greece": ("GR", EU), "Grenada": ("GD", NA),
    "Guadeloupe": ("GP", NA), "Guatemala": ("GT", NA), "Guinea": ("GN", AF), "Guinea-Bissau": ("GW", AF),
    "Guyana": ("GY", SA), "Haiti": ("HT", NA), "Honduras": ("HN", NA), "Hongkong": ("HK", AS),
    "Hungary": ("HU", EU), "Iceland": ("IS", EU), "India": ("IN", AS), "Indonesia": ("ID", AS),
    "Iran": ("IR", AS), "Iraq": ("IQ", AS), "Ireland": ("IE", EU), "Israel": ("IL", AS),
    "Italy": ("IT", EU), "Jamaica": ("JM", NA), "Japan": ("JP", AS), "Jordan": ("JO", AS),
    "Kazakhstan": ("KZ", EU), "Kenya": ("KE", AF), "Korea, North": ("KP", AS), "Korea, South": ("KR", AS),
    "Kosovo": ("XK", EU), "Kyrgyzstan": ("KG", AS), "Laos": ("LA", AS), "Latvia": ("LV", EU),
    "Lebanon": ("LB", AS), "Liberia": ("LR", AF), "Libya": ("LY", AF), "Liechtenstein": ("LI", EU),
    "Lithuania": ("LT", EU), "Luxembourg": ("LU", EU), "Macao": ("MO", AS), "Madagascar": ("MG", AF),
    "Malawi": ("MW", AF), "Malaysia": ("MY", AS), "Maldives": ("MV", AS), "Mali": ("ML", AF),
    "Malta": ("MT", EU), "Martinique": ("MQ", NA), "Mauritania": ("MR", AF), "Mauritius": ("MU", AF),
    "Mexico": ("MX", NA), "Moldova": ("MD", EU), "Monaco": ("MC", EU), "Mongolia": ("MN", AS),
    "Montenegro": ("ME", EU), "Montserrat": ("MS", NA), "Morocco": ("MA", AF), "Mozambique": ("MZ", AF),
    "Myanmar": ("MM", AS), "Netherlands": ("NL", EU), "Neukaledonien": ("NC", OC), "New Caledonia": ("NC", OC),
    "New Zealand": ("NZ", OC), "Nicaragua": ("NI", NA), "Niger": ("NE", AF), "Nigeria": ("NG", AF),
    "North Macedonia": ("MK", EU), "Northern Ireland": ("GB-NIR", EU), "Norway": ("NO", EU), "Oman": ("OM", AS),
    "Pakistan": ("PK", AS), "Palestine": ("PS", AS), "Panama": ("PA", NA), "Papua New Guinea": ("PG", OC),
    "Paraguay": ("PY", SA), "Peru": ("PE", SA), "Philippines": ("PH", AS), "Poland": ("PL", EU),
    "Portugal": ("PT", EU), "Puerto Rico": ("PR", NA), "Qatar": ("QA", AS), "Romania": ("RO", EU),
    "Russia": ("RU", EU), "Rwanda": ("RW", AF), "Réunion": ("RE", AF), "Saint-Martin": ("MF", NA),
    "San Marino": ("SM", EU), "Sao Tome and Principe": ("ST", AF), "Saudi Arabia": ("SA", AS),
    "Scotland": ("GB-SCT", EU), "Senegal": ("SN", AF), "Serbia": ("RS", EU), "Seychelles": ("SC", AF),
    "Sierra Leone": ("SL", AF), "Singapore": ("SG", AS), "Sint Maarten": ("SX", NA), "Slovakia": ("SK", EU),
    "Slovenia": ("SI", EU), "Somalia": ("SO", AF), "South Africa": ("ZA", AF), "Southern Sudan": ("SS", AF),
    "Spain": ("ES", EU), "Sri Lanka": ("LK", AS), "St. Kitts & Nevis": ("KN", NA), "St. Lucia": ("LC", NA),
    "St. Vincent & Grenadinen": ("VC", NA), "Sudan": ("SD", AF), "Suriname": ("SR", SA), "Sweden": ("SE", EU),
    "Switzerland": ("CH", EU), "Syria": ("SY", AS), "Tahiti": ("PF", OC), "Tajikistan": ("TJ", AS),
    "Tanzania": ("TZ", AF), "Thailand": ("TH", AS), "The Gambia": ("GM", AF), "Timor-Leste": ("TL", AS),
    "Togo": ("TG", AF), "Trinidad and Tobago": ("TT", NA), "Tunisia": ("TN", AF), "Turkey": ("TR", EU),
    "Turkmenistan": ("TM", AS), "Türkiye": ("TR", EU), "Uganda": ("UG", AF), "Ukraine": ("UA", EU),
    "United Arab Emirates": ("AE", AS), "United States": ("US", NA), "Uruguay": ("UY", SA),
    "Uzbekistan": ("UZ", AS), "Vanuatu": ("VU", OC), "Venezuela": ("VE", SA), "Vietnam": ("VN", AS),
    "Wales": ("GB-WLS", EU), "Yemen": ("YE", AS), "Zambia": ("ZM", AF), "Zimbabwe": ("ZW", AF),
}

# Display names that read better than Transfermarkt's.
RENAME = {"Türkiye": "Turkey", "Neukaledonien": "New Caledonia", "Hongkong": "Hong Kong",
          "St. Vincent & Grenadinen": "St. Vincent & Grenadines", "Southern Sudan": "South Sudan"}


def flag(code):
    """Flag emoji for an ISO alpha-2 code, or a UK nation subdivision like GB-ENG."""
    if code.startswith("GB-"):
        tag = "gb" + code[3:].lower()
        return "\U0001F3F4" + "".join(chr(0xE0000 + ord(c)) for c in tag) + "\U000E007F"
    if code == "XK":
        return "\U0001F1FD\U0001F1F0"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)


def lookup(name):
    """(display_name, flag_emoji, continent) for a Transfermarkt country name."""
    if not name or name not in COUNTRIES:
        return (name or "Unknown", "", "Unknown")
    code, continent = COUNTRIES[name]
    return (RENAME.get(name, name), flag(code), continent)
