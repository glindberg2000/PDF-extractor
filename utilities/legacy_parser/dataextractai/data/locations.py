"""Location data for transaction normalization."""

# Focus on NM and CA for now, expand as needed per client
LOCATIONS = {
    "states": {
        "NM": ["NEW MEXICO", "N MEX", "N.M.", "NMEX"],
        "CA": ["CALIFORNIA", "CALIF", "CAL", "CALI"],
    },
    "cities": {
        # New Mexico major cities and common variations
        "NM": [
            "ALBUQUERQUE",
            "ABQ",
            "SANTA FE",
            "LAS CRUCES",
            "RIO RANCHO",
            "LOS RANCHOS",
            "ROSWELL",
            "FARMINGTON",
            "ALAMOGORDO",
            "LOS LUNAS",
            "HOBBS",
            "CARLSBAD",
            "CLOVIS",
            "GALLUP",
            "DEMING",
            "BERNALILLO",
            "TAOS",
            "RUIDOSO",
        ],
        # California major cities
        "CA": [
            "LOS ANGELES",
            "LA",
            "SAN FRANCISCO",
            "SF",
            "SAN DIEGO",
            "SAN JOSE",
            "SACRAMENTO",
            "FRESNO",
            "OAKLAND",
            "SANTA ANA",
            "RIVERSIDE",
            "STOCKTON",
            "IRVINE",
            "BAKERSFIELD",
            "ANAHEIM",
            "SANTA CLARA",
            "BERKELEY",
        ],
    },
    # Common patterns that indicate a location
    "patterns": [
        # Address patterns
        r"\d+\s+(?:ST|STREET|AVE?|AVENUE|BLVD|BOULEVARD|RD|ROAD|LN|LANE|DR|DRIVE|CT|COURT|WAY|PLAZA|PL|PARKWAY|PKY|HWY|HIGHWAY)",
        # Directional prefixes
        r"(?:NORTH|SOUTH|EAST|WEST|N|S|E|W)\s+\w+",
        # Common location words
        r"\w+\s+(?:HEIGHTS|SPRINGS|FALLS|BEACH|VILLE|TOWN|BURG|PORT|FORT|PARK|GROVE|RIDGE|PLAZA|SQUARE|CENTER|MALL)",
    ],
}
