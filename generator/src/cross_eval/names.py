FIRST_NAMES = """
Aaron Abigail Adrian Aisha Alana Alejandro Alexis Alicia Amara Andre Angela Anika Arjun Ashley Austin Ava
Beatriz Benjamin Bianca Blake Brandon Brianna Caleb Camila Carlos Carmen Cassidy Chloe Christopher Claire
Colin Connor Dalia Damian Daniel Danielle Darius Deepa Derek Diana Dominic Elena Eli Elijah Emily Eric
Esther Ethan Evelyn Fatima Felix Fiona Gabriel Gemma Grace Hannah Hector Imani Isaac Isabel Jada Jamal
James Jasmine Javier Jenna Jeremy Jessica Joaquin Jordan Joseph Julia Julian Kara Keisha Kenji Kevin
Kiara Kyle Laila Lauren Leah Leon Liam Lucas Lucia Luis Maya Malik Marcus Maria Marisol Mason Megan Mei
Micah Miguel Mila Monica Nadia Naomi Nathan Nia Nicole Noah Nolan Olivia Omar Owen Paige Pedro Priya
Quinn Rafael Rachel Raj Rebecca Ricardo Riley Rosa Ryan Samir Samantha Sara Sean Selena Simone Sofia
Stefan Tariq Taylor Tessa Theo Tomas Trevor Valeria Victor Vivian Wesley Xavier Yara Yusuf Zara Zoe
""".split()

LAST_NAMES = """
Abbott Acosta Adeyemi Alvarez Anand Andersen Arroyo Baker Banerjee Barlow Becker Bell Bishop Boateng
Bowen Brennan Bryant Calloway Campos Carver Castillo Chandler Chen Coleman Contreras Cordova Crane
Dalton Delgado Dempsey Diaz Doyle Duarte Easton Ellison Espinoza Farrell Fischer Fleming Foster
Fuentes Garrison Gibson Goldberg Gomez Greer Gupta Hadley Hale Hammond Harlow Hayes Herrera Hoffman
Holloway Huang Ibarra Ingram Iyer Jacobs Jensen Juarez Kang Kaplan Keller Kendall Khan Kim Kowalski
Lambert Landry Larsen Lawson Leblanc Lindqvist Lopez Lowell Lucero Madsen Maldonado Mercer Meyer
Molina Montoya Moreau Morrison Nakamura Navarro Nguyen Novak Nwosu Okafor Oliveira Ortega Osei Owens
Pacheco Park Patel Pena Perez Pham Porter Quintero Ramirez Rasmussen Reyes Rhodes Rios Rivera Rojas
Rourke Salazar Sandoval Schmidt Serrano Shah Shapiro Silva Sloan Soto Stanton Sullivan Tanaka Thornton
Torres Tran Ulrich Underwood Vance Vargas Vasquez Velasquez Voss Wagner Walsh Ward Whitaker Yamamoto
Yilmaz Young Zamora Zhang Ziegler
""".split()

# Coined company stems: two invented halves, so client names don't collide with real firms.
COMPANY_HEADS = """
Alder Amber Arc Aster Basal Bayl Birch Bright Brook Calder Cedar Cind Clear Cobal Copper Corv Crest Dell
Delt Drift Elm Ember Fern Fjord Flint Garn Glen Granit Halc Harbor Haven Helio Hollow Iron Juni Kest
Lark Lumen Mar Merid Mist North Oak Onyx Orrin Pell Pine Quarr Quill Raven Ridge Rook Sable Sedge Silv
Sorrel Stone Strat Tamar Thistle Torr Vale Verd Wend Wick Wren Yarrow Zephr
""".split()
COMPANY_TAILS = """
bay beam bridge brook crest dale field ford gate grove harbor hart haven holt lane ley line mark mere
mont more point port ridge rock run shore side stead ton vale view wood worth
""".split()

INDUSTRY_WORDS = {
    "Software": ["Software", "Analytics", "Systems", "Cloud", "Data", "Labs"],
    "Pharma": ["Therapeutics", "Biosciences", "Pharma", "Bio"],
    "Financial Services": ["Capital", "Financial", "Partners", "Bancorp", "Advisors"],
    "Manufacturing": ["Industries", "Manufacturing", "Components", "Fabrication"],
    "Healthcare": ["Health", "Medical", "Care Partners"],
    "Retail": ["Brands", "Retail Group", "Outfitters", "Goods"],
    "Energy": ["Energy", "Power", "Renewables"],
    "Nonprofit": ["Foundation", "Alliance", "Society"],
    "Higher Education": ["University", "College", "Institute"],
    "Automotive": ["Motors", "Automotive", "Mobility"],
    "Insurance": ["Insurance", "Mutual", "Assurance"],
    "Telecom": ["Networks", "Communications", "Telecom"],
}

LEGAL_SUFFIXES = ["Inc.", "LLC", "Corp.", "Co.", "Group, Inc.", "Holdings, LLC"]

VENUE_PATTERNS = [
    "{a} Grand Hotel", "{a} Convention Center", "The {a} Ballroom", "{a} Conference Center",
    "{a} Exposition Hall", "Hotel {a}", "{a} Resort & Spa", "{a} Pavilion", "{a} Event Center",
]
VENUE_WORDS = """
Lakeshore Riverside Union Meridian Summit Harborview Ironworks Foundry Crescent Parkside Gateway Canal
Prairie Bluebird Lantern Granite Westbrook Larkspur Copperline Fairmount Highland Market Station Juniper
Beacon Northgate Riverbend Trinity Lockhart Sterling
""".split()

OFFICE_CITIES = {
    "CHI": [("Chicago", "IL"), ("Evanston", "IL"), ("Schaumburg", "IL"), ("Milwaukee", "WI"), ("Indianapolis", "IN"), ("Detroit", "MI")],
    "NSH": [("Nashville", "TN"), ("Franklin", "TN"), ("Atlanta", "GA"), ("Louisville", "KY"), ("Memphis", "TN")],
    "DEN": [("Denver", "CO"), ("Boulder", "CO"), ("Salt Lake City", "UT"), ("Phoenix", "AZ"), ("Colorado Springs", "CO")],
    "TOR": [("Toronto", "ON"), ("Mississauga", "ON"), ("Ottawa", "ON"), ("Montreal", "QC")],
}
