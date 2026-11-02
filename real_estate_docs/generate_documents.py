#!/usr/bin/env python3
"""
Generate a fictitious, deliberately disorganised collection of 1,000 real estate
PDF documents for an "organise this with AI" classroom exercise.

* ~130 invented properties, 12 property types, 28 document types
* Every property has several different document types (and some repeats)
* Every PDF has a random length of 1-15 pages
* File names are meaningless ("scan_20230815_0931.pdf", "IMG_4821.pdf", ...)
  and everything lands in one flat folder, so the only way to organise the
  files is to READ them.
* An instructor answer key (CSV) is written to a separate folder.

Usage:  python3 generate_documents.py [--seed 20261102] [--count 1000]
"""
import argparse, csv, datetime as dt, os, re, shutil
import random
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.doctemplate import LayoutError

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = letter
MX, BOT, TOP = 54, 58, 735
FW, FH = W - 2 * MX, TOP - BOT
R = random.Random()

# --------------------------------------------------------------------------
# Name pools (all invented)
# --------------------------------------------------------------------------
PTYPES = ["Multifamily", "Office", "Industrial", "Retail", "Self Storage", "Hotel",
          "Senior Housing", "Medical Office", "Student Housing", "Mixed-Use",
          "Data Center", "Single-Family Rental"]
RES = {"Multifamily", "Student Housing", "Single-Family Rental", "Senior Housing"}
COM = {"Office", "Industrial", "Retail", "Medical Office", "Mixed-Use", "Data Center"}

NAME_WORDS = """Maple Cedar Harbor Summit Willow Granite Lakeshore Riverbend Oakmont Prairie Sterling Beacon
Juniper Copper Magnolia Ironwood Cobalt Pinecrest Westgate Eastlake Aspen Birchwood Bayview Cypress Dover
Falcon Garnet Heritage Highland Kingsley Laurel Meridian Northgate Orchard Parkview Quarry Redwood Sable
Timberline Union Vista Wexford Yarrow Zephyr Amberly Brookside Canyon Driftwood Elmhurst Foxglove Glenview
Hollis Indigo Jasper Keystone Lantern Mesa Nautilus Onyx Pelican Quincy Ridgeline Saddlebrook Tidewater
Upland Valley Whitaker Alder Bluestone Crestline Dunmore Everett Fairmont Gatewood Hawthorne Ivy Kestrel
Lockwood Marlow Newport Osprey Palisade Raven Stonebridge Thornton Verde Windmill Ashford Banyan Calloway""".split()
SUFFIX = {
    "Multifamily": ["Apartments", "Flats", "Residences", "Lofts", "Villas", "Commons", "Terrace"],
    "Office": ["Plaza", "Tower", "Office Center", "Office Park", "Corporate Center"],
    "Industrial": ["Logistics Center", "Distribution Center", "Commerce Park", "Industrial Park", "Business Park"],
    "Retail": ["Shopping Center", "Marketplace", "Crossing", "Square", "Town Center"],
    "Self Storage": ["Self Storage", "Storage Depot", "Secure Storage"],
    "Hotel": ["Inn & Suites", "Hotel", "Lodge", "Suites"],
    "Senior Housing": ["Senior Living", "Gardens", "Manor", "Assisted Living"],
    "Medical Office": ["Medical Pavilion", "Health Center", "Medical Plaza"],
    "Student Housing": ["Student Living", "Collegiate Commons", "Scholars Hall"],
    "Mixed-Use": ["Mixed-Use Center", "Market Lofts", "Station District", "Village"],
    "Data Center": ["Data Campus", "Data Center", "Technology Campus"],
    "Single-Family Rental": ["Homes", "Rental Homes", "Cottages"],
}
CITIES = [("Columbus", "OH"), ("Indianapolis", "IN"), ("Nashville", "TN"), ("Charlotte", "NC"), ("Raleigh", "NC"),
          ("Phoenix", "AZ"), ("Tempe", "AZ"), ("Dallas", "TX"), ("Austin", "TX"), ("Houston", "TX"), ("San Antonio", "TX"),
          ("Denver", "CO"), ("Aurora", "CO"), ("Atlanta", "GA"), ("Savannah", "GA"), ("Tampa", "FL"), ("Orlando", "FL"),
          ("Jacksonville", "FL"), ("Kansas City", "MO"), ("St. Louis", "MO"), ("Minneapolis", "MN"), ("Milwaukee", "WI"),
          ("Madison", "WI"), ("Chicago", "IL"), ("Naperville", "IL"), ("Detroit", "MI"), ("Grand Rapids", "MI"),
          ("Cleveland", "OH"), ("Cincinnati", "OH"), ("Pittsburgh", "PA"), ("Philadelphia", "PA"), ("Allentown", "PA"),
          ("Baltimore", "MD"), ("Richmond", "VA"), ("Norfolk", "VA"), ("Boston", "MA"), ("Hartford", "CT"),
          ("Albany", "NY"), ("Buffalo", "NY"), ("Newark", "NJ"), ("Salt Lake City", "UT"), ("Boise", "ID"),
          ("Portland", "OR"), ("Seattle", "WA"), ("Sacramento", "CA"), ("San Diego", "CA"), ("Riverside", "CA"),
          ("Las Vegas", "NV"), ("Albuquerque", "NM"), ("Oklahoma City", "OK"), ("Louisville", "KY"), ("Memphis", "TN"),
          ("Birmingham", "AL"), ("New Orleans", "LA"), ("Omaha", "NE"), ("Des Moines", "IA"), ("Greenville", "SC")]
STREETS = ["Maple", "Industrial", "Commerce", "Lakeview", "Ridge", "Meadow", "Centennial", "Airport", "Harbor", "Mill",
           "Church", "Highland", "Market", "Pioneer", "Sunset", "University", "Railroad", "Cherry", "Elm", "Grand",
           "Liberty", "Heritage", "Quarry", "Peachtree", "Bridge", "Orchard", "Station", "Technology", "Medical Center"]
STYPES = ["Road", "Avenue", "Drive", "Parkway", "Boulevard", "Street", "Way", "Lane", "Court"]

FIRST = """James Maria Robert Linda Michael Priya David Susan Carlos Emily Daniel Aisha Kevin Olivia Brian Hannah Marcus Sofia
Anthony Grace Jerome Natalie Victor Chloe Raymond Elena Tyrone Megan Samuel Fatima Patrick Julia Andre Rachel Hector Tina""".split()
LAST = """Alvarez Brooks Chen Delgado Evans Foster Garcia Hughes Ito Jackson Kowalski Lopez Mitchell Nguyen Okafor Patel
Quinn Ramirez Schmidt Thompson Underwood Vasquez Walker Xu Young Zimmerman Bennett Coleman Dixon Harper Larsen Moreno""".split()
TEN_A = """Brightline Harlow Northstar Pioneer Evergreen Redwood Keystone Atlas Blue-Heron Cardinal Lighthouse Ironclad
Summit-View Bluebird Crescent Paragon Westbrook Silverline Oakleaf Trident Granger Lumen Fairway Orbit""".replace("-", " ").split()
TEN_B = {
    "Office": ["Financial Group", "Law Group", "Engineering", "Staffing", "Insurance Agency", "Consulting LLC", "Software Inc.", "Advisors"],
    "Industrial": ["Logistics LLC", "Wholesale", "Supply Co.", "Freight Lines", "Packaging Inc.", "Distribution", "Fulfillment", "Manufacturing"],
    "Retail": ["Coffee Co.", "Pharmacy", "Fitness", "Bakery", "Nail Studio", "Pizza Kitchen", "Dry Cleaners", "Pet Supply"],
    "Medical Office": ["Dental", "Pediatrics", "Orthopedics", "Imaging", "Family Medicine", "Physical Therapy", "Dermatology", "Cardiology"],
    "Mixed-Use": ["Coffee Co.", "Fitness", "Law Group", "Bakery", "Design Studio", "Wine Bar", "Salon", "Realty"],
    "Data Center": ["Cloud Services", "Networks", "Hosting", "Data Systems", "Telecom", "Compute Inc."],
}
SELLERS = ["Harlan Street Capital", "Corvina Realty Partners", "Midlands Property Trust", "Ardent Hollow Holdings", "Fenwick & Dale Investments",
           "Tallgrass Equity Group", "Pemberton Real Estate Fund III", "Lakeside Family Partnership", "Northvale Development Co.", "Brandt Ridge Properties",
           "Orchid Bay Ventures", "Stonehaven Asset Partners", "Redfern Holdings LP", "Gable Point Capital", "Ellison Crest Realty"]
BUYERS = ["Cascadia Rock Capital", "Vireo Income Properties", "Anchorage Meadow Partners", "Beacon Hollow Investors", "Tidewater Core Fund",
          "Granite Lane Realty", "Sunbelt Ridge Acquisitions", "Keel & Compass Properties", "Whitfield Park Capital", "Juniper Peak Real Estate Fund"]
LENDERS = ["Tri-County Savings Bank", "Alder Life Insurance Company", "Northfield Commercial Bank", "Summit Trail Credit Union",
           "Harbor Mutual Life", "First Prairie National Bank", "Redstone Capital Finance", "Lakeland Agency Lending", "Cobalt Bridge Lending"]
APPRAISERS = ["Calloway & Reid Valuation Group", "Hartwell Appraisal Associates", "Meridian Valuation Advisors", "Pinnacle Realty Appraisers", "Stone & Marsh Appraisal"]
ENVCOS = ["TerraSound Environmental", "Greenfield Environmental Consultants", "Bluewater Site Sciences", "Cairn Environmental Group", "Ridgeway Geo-Environmental"]
ENGCOS = ["Keystone Building Consultants", "Harmon & Pike Engineering", "Structura Property Assessments", "Lindqvist Engineering Group", "Northbridge Inspection Services"]
TITLECOS = ["Continental Abstract & Title", "Heartland Title Insurance Co.", "Patriot Land Title", "Evergreen Title Services", "Cornerstone Title Agency"]
SURVEYORS = ["Axis Land Surveying", "Meridian Survey & Mapping", "Boundary Line Surveyors", "Compass Point Geomatics"]
BROKERS = ["Westmoor Capital Markets", "Ashby Dunn Brokerage", "Pelham Rowe Advisors", "Granger & Bell Investment Sales", "Harborview Realty Advisors"]
INSURERS = ["Great Lakes Mutual", "Keystone Casualty", "Allied Heritage Insurance", "Prairie State Indemnity", "Blue Ridge Underwriters", "Sentinel Property & Casualty"]
INSBRK = ["Marlowe & Finch Insurance Brokers", "Cardinal Risk Partners", "Tandem Risk Advisors"]
PMCOS = ["Redwood Property Management", "Harbor Point Management Group", "Elmstead Asset Services", "Cobblestone Property Co.", "Lumen Residential Services", "Orion Commercial Management"]
VENDORS = [("Apex Elevator Service", "elevator maintenance"), ("GreenEdge Landscaping", "landscape maintenance"), ("ClearPath Janitorial", "janitorial services"),
           ("Summit HVAC Solutions", "HVAC preventive maintenance"), ("SafeGuard Fire & Life Safety", "fire alarm and sprinkler inspection"),
           ("Brightway Pest Control", "pest control"), ("NorthStar Security Patrol", "security patrol services"), ("WasteWise Hauling", "waste and recycling removal"),
           ("PolarClean Pressure Washing", "exterior cleaning"), ("Ironside Snow & Ice", "snow and ice removal"), ("PaveRight Sealcoating", "parking lot maintenance"),
           ("BlueDrop Pool Services", "pool maintenance"), ("Spectrum Roofing", "roof repair and maintenance")]
HOTEL_FLAGS = ["Meridian Select", "Harborlight Suites", "Crestwood Inn", "Brookline Collection", "Sunrise Express"]
LAWFIRMS = ["Whitcomb Lyle LLP", "Aldridge & Voss PLLC", "Pratt Henley Stone LLP", "Doyle Marchand LLP"]
ACCENTS = ["#1f3a5f", "#2d5a3d", "#6b2737", "#3b3b6d", "#7a4a12", "#14555a", "#4a4a4a", "#5a2d6b"]

# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def usd(x, dec=0):
    return ("-$" if x < 0 else "$") + f"{abs(x):,.{dec}f}"

def num(x):
    return f"{x:,.0f}"

def dstr(d):
    return d.strftime("%B %-d, %Y")

def sdate(d):
    return d.strftime("%m/%d/%Y")

def rdate(a, b):
    return a + dt.timedelta(days=R.randint(0, max(0, (b - a).days)))

def person():
    return f"{R.choice(FIRST)} {R.choice(LAST)}"

def esc(t):
    return re.sub(r"&(?!amp;|lt;|gt;)", "&amp;", str(t))

def rv():
    return dict(pct=f"{R.uniform(2, 14):.1f}", pct2=f"{R.uniform(88, 97):.1f}", pct3=f"{R.uniform(3, 8):.1f}",
                amt=usd(R.randint(8, 480) * 1000), n=R.randint(2, 48), yrs=R.randint(3, 12), mi=R.randint(1, 9),
                rate=f"{R.uniform(4.1, 7.6):.2f}", cap=f"{R.uniform(5.0, 8.2):.2f}", psf=f"{R.uniform(6, 48):.2f}",
                dow=R.choice(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]),
                yr=R.randint(2019, 2026), person=person(), q=R.choice(["1Q", "2Q", "3Q", "4Q"]))

def fmt(t, ctx):
    return t.format(**ctx, **rv())

# --------------------------------------------------------------------------
# Property generation
# --------------------------------------------------------------------------
def make_properties(n):
    used, props = set(), []
    for i in range(n):
        pt = PTYPES[i % len(PTYPES)] if i < 36 else R.choice(PTYPES)
        while True:
            name = f"{R.choice(NAME_WORDS)} {R.choice(NAME_WORDS)} {R.choice(SUFFIX[pt])}" if R.random() < 0.25 \
                else f"{R.choice(NAME_WORDS)} {R.choice(SUFFIX[pt])}"
            if name not in used and not any(name.split()[0] == u.split()[0] and name.split()[-1] == u.split()[-1] for u in used):
                used.add(name)
                break
        city, st = R.choice(CITIES)
        p = dict(pid=f"P{i+1:03d}", name=name, ptype=pt, city=city, state=st,
                 street=f"{R.randint(100, 9800)} {R.choice(STREETS)} {R.choice(STYPES)}",
                 zip=f"{R.randint(10000, 99950):05d}", year=R.randint(1962, 2023))
        p["address"] = f"{p['street']}, {city}, {st} {p['zip']}"
        if pt == "Multifamily":
            p["units"] = R.randint(48, 420); p["avg_sf"] = R.randint(720, 1050)
            p["price"] = p["units"] * R.randint(110, 260) * 1000; p["rent"] = R.randint(1050, 2450)
        elif pt == "Student Housing":
            p["units"] = R.randint(120, 640); p["avg_sf"] = R.randint(330, 520)
            p["price"] = p["units"] * R.randint(70, 130) * 1000; p["rent"] = R.randint(780, 1350)
        elif pt == "Single-Family Rental":
            p["units"] = R.randint(24, 210); p["avg_sf"] = R.randint(1150, 2100)
            p["price"] = p["units"] * R.randint(220, 380) * 1000; p["rent"] = R.randint(1600, 2900)
        elif pt == "Senior Housing":
            p["units"] = R.randint(60, 220); p["avg_sf"] = R.randint(460, 800)
            p["price"] = p["units"] * R.randint(150, 300) * 1000; p["rent"] = R.randint(3800, 7600)
        elif pt == "Hotel":
            p["units"] = R.randint(72, 260); p["avg_sf"] = 420
            p["price"] = p["units"] * R.randint(100, 260) * 1000; p["rent"] = R.randint(105, 235)  # ADR
        elif pt == "Self Storage":
            p["units"] = R.randint(280, 900); p["avg_sf"] = R.randint(95, 140)
            p["price"] = p["units"] * p["avg_sf"] * R.randint(90, 160); p["rent"] = R.randint(85, 190)
        else:
            sf = R.randint(18, 420) * 1000
            p["units"] = R.randint(4, 40) if pt != "Industrial" else R.randint(1, 8)
            p["avg_sf"] = sf // p["units"]
            ppsf = dict(Office=(150, 350), Industrial=(80, 160), Retail=(120, 300), **{"Medical Office": (250, 450)},
                        **{"Mixed-Use": (200, 400)}, **{"Data Center": (600, 1200)})[pt]
            p["price"] = sf * R.randint(*ppsf)
            p["rent"] = dict(Office=(22, 48), Industrial=(6, 11), Retail=(14, 38), **{"Medical Office": (26, 42)},
                             **{"Mixed-Use": (20, 35)}, **{"Data Center": (150, 220)})[pt]
            p["rent"] = R.randint(*p["rent"])
        p["sf"] = p["units"] * p["avg_sf"]
        p["price"] = round(p["price"], -4)
        p["unit_word"] = dict(Multifamily="apartment homes", **{"Student Housing": "beds", "Single-Family Rental": "homes",
                              "Senior Housing": "units", "Hotel": "guest rooms", "Self Storage": "storage units"}).get(pt, "rentable square feet")
        p["size"] = (f"{p['units']:,} {p['unit_word']}" if pt in RES | {"Hotel", "Self Storage"} else f"{p['sf']:,} SF")
        p["acq"] = rdate(dt.date(2018, 3, 1), dt.date(2024, 9, 30))
        p["owner"] = f"{name.split(' Inn')[0].split(' &')[0]} Owner LLC"
        p["seller"], p["buyer"] = R.choice(SELLERS), R.choice(BUYERS)
        p["lender"], p["manager"] = R.choice(LENDERS), R.choice(PMCOS)
        p["loan"] = round(p["price"] * R.uniform(0.5, 0.68), -4)
        p["rate_"] = round(R.uniform(3.6, 7.4), 2)
        p["noi"] = p["price"] * R.uniform(0.052, 0.077)
        p["rev"] = p["noi"] / R.uniform(0.5, 0.64)
        p["flag"] = R.choice(HOTEL_FLAGS)
        p["tenants"] = R.randint(3, 30)
        props.append(p)
    return props

# --------------------------------------------------------------------------
# Narrative / clause text banks
# --------------------------------------------------------------------------
FLAVOR = {
    "Multifamily": ["The community offers a resort-style pool, fitness center, resident clubhouse, package lockers and a dog park.",
                    "Unit interiors feature quartz countertops, stainless appliances, in-unit washer and dryer and plank flooring in select renovated homes.",
                    "Average in-place rent is {rentu} per month against an average unit size of {avgsf} square feet.",
                    "Resident turnover has averaged {pct}% annually with renewal retention above {pct2}%."],
    "Student Housing": ["The community is leased by the bed on individual lease liability with parent guaranties and furnished units.",
                        "The property is located {mi} blocks from the main campus with a dedicated shuttle serving fall and spring terms.",
                        "Pre-leasing for the coming academic year stands at {pct2}% with rental rates per bed averaging {rentu}.",
                        "Amenities include study lounges, a rooftop terrace, 24-hour fitness and a game room."],
    "Single-Family Rental": ["The portfolio consists of detached single-family homes in a scattered-site pattern, each with attached garage and fenced yard.",
                             "Homes average {avgsf} square feet with average monthly rent of {rentu}.",
                             "Turn costs average {amt} per home, and the in-house maintenance team handles most work orders within {n} days."],
    "Senior Housing": ["The community provides assisted living and memory care services under a state-issued license with {n} full-time caregivers per shift.",
                       "Average monthly revenue per occupied unit is {rentu}, inclusive of base rent and levels of care.",
                       "Occupancy stands at {pct2}% with an average resident length of stay of {yrs} years.",
                       "Dining, housekeeping, transportation and activities programming are included in the base fee."],
    "Hotel": ["The hotel operates under a franchise agreement with {flag}, with a complimentary breakfast, indoor pool and {n} meeting rooms.",
              "Trailing twelve-month occupancy was {pct2}% with an average daily rate of {rentu} and RevPAR indexing above the competitive set.",
              "Revenue is driven by transient corporate demand, group business and weekend leisure travel.",
              "A product improvement plan for guest rooms and corridors is scheduled under the brand standards."],
    "Self Storage": ["The facility offers climate-controlled and drive-up units, a manager's office, keypad gate access and video surveillance.",
                     "Physical occupancy is {pct2}% and the average in-place rent is {rentu} per unit per month.",
                     "Ancillary income includes tenant insurance, merchandise sales and truck rental commissions.",
                     "Unit sizes range from 5x5 to 10x30 and the property is managed by an on-site team with online rental capability."],
    "Office": ["The building features a renovated lobby, structured parking at a ratio of {n} per 1,000 square feet, and a tenant lounge with fitness center.",
               "Weighted average lease term remaining is {yrs} years and in-place rents average {rentu} per square foot, full service gross.",
               "Floor plates are efficient and column-spacing supports open and private-office layouts.",
               "The building is served by redundant elevators, a backup generator and a high-efficiency chiller plant."],
    "Industrial": ["The building offers {n}' clear height, ESFR sprinklers, dock-high and drive-in doors, and a secured truck court with trailer parking.",
                   "In-place rents average {rentu} per square foot triple net with 3% annual escalations.",
                   "The facility is located {mi} miles from the interstate with access to a regional intermodal terminal.",
                   "Cross-dock and rear-load configurations allow for flexible multi-tenant demising."],
    "Retail": ["The center is anchored by a grocery tenant and supported by in-line shop space, pads and an outparcel ground lease.",
               "Tenants pay percentage rent in addition to base rent and reimburse CAM, taxes and insurance on a triple net basis.",
               "Average rent is {rentu} per square foot with parking at a ratio of {n} spaces per 1,000 square feet.",
               "Co-tenancy provisions in the anchor lease are triggered if occupancy falls below 70%."],
    "Medical Office": ["The building is configured for physician practices with plumbing in every suite, imaging-ready floor loads and dedicated medical waste storage.",
                       "The property is located adjacent to a regional hospital campus and benefits from referral-driven tenancy.",
                       "Rents average {rentu} per square foot modified gross and leases include tenant improvement allowances for specialized buildout.",
                       "Patient parking and ADA-compliant access are provided at a ratio of {n} spaces per 1,000 square feet."],
    "Mixed-Use": ["The project combines ground-floor retail and restaurant space with upper-level residential and office components.",
                  "Residential units are leased on 12-month terms while the commercial component is leased on a triple net basis.",
                  "The property is walkable to transit, with {n} structured parking spaces shared between uses.",
                  "Percentage rent and CAM reimbursements are tracked separately for the commercial component."],
    "Data Center": ["The facility is a purpose-built data center with {n} MW of critical IT load, N+1 power and cooling redundancy, and dual utility feeds.",
                    "Tenants are billed per kilowatt of contracted capacity with power pass-through at metered cost.",
                    "On-site infrastructure includes diesel generators, UPS systems, CRAC units and a biometric-controlled security perimeter.",
                    "Carrier-neutral meet-me room supports multiple fiber providers."],
}
NARR = {
    "market": ["{name} is located in {city}, {state}, a market that has recorded {pct}% population growth over the last five years.",
               "The {city} {ptype} market has experienced absorption of {n}00 thousand square feet or equivalent units over the trailing twelve months, outpacing new deliveries.",
               "Market vacancy for comparable {ptype} product stands at {pct}%, down from {pct3}% two years ago.",
               "Employment growth is led by healthcare, logistics, education and professional services sectors.",
               "New construction starts have decelerated due to higher financing costs and tighter lending standards, which supports the existing supply.",
               "Median household income within a {mi}-mile radius of the property is approximately {amt} and has grown {pct}% annually.",
               "Rent growth in the submarket has averaged {pct3}% annually over the past {yrs} years.",
               "Investor demand for {ptype} assets in {city} remains strong with recent trades at capitalization rates between {cap}% and {cap}%."],
    "site": ["The site contains approximately {n}.{n} acres and is generally level with frontage along {street}.",
             "Access to the site is provided by {n} curb cuts and the property is served by municipal water and sanitary sewer.",
             "The site is not located within a designated 100-year floodplain according to the FEMA flood map in effect.",
             "Soils are typical of the region and no evidence of unsuitable conditions was observed at the time of inspection.",
             "Surrounding land uses include residential, commercial and light industrial properties of similar vintage.",
             "Utilities, including electric, natural gas and telecommunications, are available to the site from the street."],
    "building": ["{name} was originally constructed in {year} and consists of {size} in a building of {n} stories.",
                 "The structure is of wood-frame, masonry and steel-frame construction on a slab-on-grade foundation.",
                 "The roof is a {n}-year membrane system with an estimated remaining useful life of {yrs} years.",
                 "Mechanical systems include rooftop package units and central plant equipment of varying age.",
                 "Exterior finishes comprise brick veneer, fiber-cement siding and aluminum storefront glazing in good condition.",
                 "Common area interiors have been refreshed within the last {yrs} years and are in average to good condition.",
                 "Life-safety systems include a fully sprinklered building, addressable fire alarm panel and emergency lighting."],
    "env": ["A review of regulatory databases identified no listings for the subject property within the ASTM-specified search distances.",
            "No recognized environmental conditions (RECs) were identified in connection with the subject property.",
            "Historical sources indicate the site was previously used for agricultural and light commercial purposes.",
            "A former dry cleaner located {mi} blocks to the north is listed as a closed case and is not expected to impact the site.",
            "No evidence of underground storage tanks, stained soils or stressed vegetation was observed during the site reconnaissance.",
            "Based on the age of construction, an asbestos operations and maintenance program is recommended for suspect materials.",
            "Vapor encroachment screening did not identify a condition requiring further evaluation."],
    "fin": ["Effective gross income for the trailing period was {amt}, representing a {pct}% increase over the prior year.",
            "Operating expenses totaled {amt} or approximately {psf} per square foot, with real estate taxes representing the largest line item.",
            "Net operating income is projected to grow at a compound annual rate of {pct3}% over the hold period.",
            "The going-in capitalization rate of {cap}% reflects the in-place income and the stabilized occupancy assumption.",
            "Management fees are calculated at {pct3}% of collected revenue and are included in operating expenses.",
            "A reserve for replacements of $250 per unit has been underwritten in the cash flow below net operating income.",
            "Debt service coverage ratio was {cap}x on a trailing basis against a covenant minimum of 1.20x."],
    "ops": ["On-site staffing consists of a property manager, assistant manager, maintenance supervisor and {n} additional team members.",
            "The manager completes a monthly walk of the property and submits a variance report to the owner by the {n}th business day.",
            "Service requests are tracked through a work-order system with an average completion time of {n} hours.",
            "Preventive maintenance schedules for HVAC, elevators and life-safety systems were completed on time during the period.",
            "Marketing efforts include digital listings, signage, broker outreach and a resident referral program.",
            "Collections for the period were {pct2}% of billed charges, with bad debt of {pct3}% of gross potential income."],
    "inv": ["The investment thesis is based on stabilizing occupancy, completing the capital plan and capturing rent growth to market.",
            "The business plan contemplates a hold period of {yrs} years with disposition upon achievement of target returns.",
            "Projected levered IRR is {pct}% with an equity multiple of 1.{n}x over the hold period.",
            "Distributions to investors for the quarter were paid at an annualized rate of {pct3}% on contributed capital.",
            "Key risks include interest rate exposure, tenant rollover, construction cost overruns and local supply additions.",
            "Leasing velocity improved during the period and management expects further upward pressure on in-place rents."],
    "cond": ["The roofing system exhibits localized ponding and sealant deterioration; spot repairs are recommended within 12 months.",
             "Asphalt paving shows alligator cracking and should be sealcoated and restriped during the next {n} months.",
             "Domestic water piping is copper and PVC with no evidence of widespread leakage.",
             "Electrical service is adequate for current demand; select panels are nearing the end of their useful life.",
             "Elevators were last modernized {yrs} years ago and are operating without deficiency.",
             "ADA observations include non-compliant slopes at two accessible routes and signage at parking; cost to cure is estimated at {amt}.",
             "Windows and exterior doors are in fair condition; sealant replacement is recommended at selected locations."],
    "reg": ["The property is zoned in accordance with the {city} Unified Development Ordinance and the current use is a legally permitted use.",
            "Setback, height, parking and lot coverage requirements are satisfied based on the information provided by the municipality.",
            "There are no open building code violations or pending special assessments on file with the municipality as of the date of this letter.",
            "The zoning ordinance permits rebuilding to current density if the improvements are destroyed by casualty.",
            "A certificate of occupancy was issued on file for the existing improvements.",
            "Parking is conforming with {n} spaces provided versus {n} spaces required by code."],
}
HEADS = {"market": ["Market Overview", "Submarket Analysis", "Supply and Demand", "Demographics and Employment"],
         "site": ["Site Description", "Access and Utilities", "Topography and Flood Zone"],
         "building": ["Improvements Description", "Building Systems", "Construction Details"],
         "env": ["Records Review", "Site Reconnaissance", "Findings and Opinions", "Historical Use"],
         "fin": ["Financial Analysis", "Income and Expense Review", "Valuation Discussion", "Operating Performance"],
         "ops": ["Property Operations", "Management Commentary", "Leasing and Marketing"],
         "inv": ["Investment Overview", "Business Plan Progress", "Investor Distributions", "Risk Considerations"],
         "cond": ["Observed Conditions", "Deferred Maintenance", "Recommendations"],
         "reg": ["Zoning Classification", "Code Compliance", "Permitted Uses and Parking"]}

LEGAL_FILL = [
    "Notwithstanding anything to the contrary contained herein, the parties agree that the foregoing shall be construed in accordance with the laws of the State of {state}.",
    "All notices required or permitted hereunder shall be in writing and delivered by certified mail, nationally recognized overnight courier or electronic mail with confirmation of receipt.",
    "Time is of the essence with respect to each and every provision of this instrument.",
    "No waiver of any provision shall be effective unless in writing and signed by the party against whom such waiver is sought.",
    "If any term is held invalid or unenforceable, the remaining terms shall continue in full force and effect.",
    "This instrument shall be binding upon and inure to the benefit of the parties and their respective successors and permitted assigns.",
    "Each party represents that it has full power and authority to enter into and perform its obligations hereunder.",
    "The prevailing party in any action to enforce the terms hereof shall be entitled to recover reasonable attorneys' fees and costs."]
BANKS = {
 "psa": [("Purchase and Sale", "Seller agrees to sell and Buyer agrees to purchase the Property known as {name}, located at {address}, consisting of {size}, together with all improvements, fixtures and appurtenances."),
         ("Purchase Price", "The purchase price for the Property shall be {price}, payable at Closing by wire transfer of immediately available funds, subject to the prorations and adjustments set forth herein."),
         ("Earnest Money Deposit", "Within {n} business days after the Effective Date, Buyer shall deposit {dep} with the Escrow Agent. The deposit shall become non-refundable upon expiration of the Due Diligence Period except as expressly provided."),
         ("Due Diligence Period", "Buyer shall have {n} days following the Effective Date to inspect the Property, review the Due Diligence Materials and terminate this Agreement in its sole discretion."),
         ("Title and Survey", "Seller shall convey good and marketable fee simple title to the Property by special warranty deed, subject only to the Permitted Exceptions."),
         ("Representations and Warranties of Seller", "Seller represents that the rent roll delivered to Buyer is true, correct and complete in all material respects and that there are no pending or threatened condemnation or litigation proceedings."),
         ("Operation of the Property", "Between the Effective Date and Closing, Seller shall operate the Property in the ordinary course and shall not enter into new leases or service contracts without Buyer's approval."),
         ("Conditions to Closing", "Buyer's obligation to close is conditioned upon delivery of tenant estoppel certificates from tenants representing at least 75% of leased area and issuance of the title policy."),
         ("Prorations", "Rents, real estate taxes, utilities and operating expenses shall be prorated as of 11:59 p.m. on the day preceding Closing based on the actual number of days in the period."),
         ("Closing", "Closing shall occur on or before {close}, through escrow with {title}. Possession shall be delivered to Buyer at Closing."),
         ("Casualty and Condemnation", "If the Property is materially damaged prior to Closing, Buyer may terminate this Agreement or proceed to close and receive an assignment of insurance proceeds.")],
 "lease": [("Premises", "Landlord leases to Tenant, and Tenant leases from Landlord, the Premises described in the Basic Lease Information located at {name}, {address}."),
           ("Term", "The term of this Lease shall be {yrs} years commencing on the Commencement Date, unless sooner terminated or extended pursuant to the terms hereof."),
           ("Base Rent", "Tenant shall pay monthly Base Rent in the amounts set forth in the Rent Schedule, in advance, on the first day of each calendar month, without demand, deduction or offset."),
           ("Additional Rent and Operating Expenses", "Tenant shall pay its Proportionate Share of Operating Expenses, Real Estate Taxes and Insurance Costs, estimated monthly and reconciled annually."),
           ("Security Deposit", "Upon execution, Tenant shall deposit with Landlord a security deposit equal to {n} months of Base Rent, to be held without interest."),
           ("Use", "The Premises shall be used solely for the Permitted Use and for no other purpose without Landlord's prior written consent."),
           ("Maintenance and Repairs", "Landlord shall maintain the roof, structure and common areas. Tenant shall maintain the interior of the Premises, including HVAC equipment exclusively serving the Premises."),
           ("Alterations", "Tenant shall not make any alterations costing more than {amt} without Landlord's prior written consent, which shall not be unreasonably withheld."),
           ("Insurance and Indemnity", "Tenant shall maintain commercial general liability insurance of not less than $2,000,000 per occurrence naming Landlord and Landlord's lender as additional insureds."),
           ("Assignment and Subletting", "Tenant shall not assign this Lease or sublet all or any part of the Premises without Landlord's prior written consent."),
           ("Default and Remedies", "If Tenant fails to pay rent within five days of written notice, or fails to cure any other default within thirty days, Landlord may terminate this Lease and pursue all remedies at law."),
           ("Renewal Option", "Tenant shall have {n} option(s) to renew for {yrs} years each at the then-prevailing market rent upon at least nine months' notice."),
           ("Subordination and Estoppel", "This Lease is subordinate to any mortgage now or hereafter encumbering the Property, and Tenant shall deliver an estoppel certificate within ten days of request.")],
 "reslease": [("Parties and Premises", "This Residential Lease is between {owner} (\"Landlord\") and the Resident named herein for the dwelling at {name}, {address}."),
              ("Term and Rent", "The lease term is {n} months. Monthly rent is due on the first day of each month, with a late charge of 5% assessed after the {n}th day."),
              ("Security Deposit", "Resident has paid a refundable security deposit which shall be returned within thirty days after move-out less lawful deductions for damages beyond normal wear."),
              ("Utilities and Fees", "Resident is responsible for electricity and internet. Water, sewer and trash are billed back through a monthly utility fee."),
              ("Occupancy", "The dwelling shall be occupied only by the persons listed on this lease. Guests staying more than fourteen days require written consent."),
              ("Pets", "No animals are permitted without a signed Pet Addendum, a nonrefundable pet fee and monthly pet rent."),
              ("Maintenance and Entry", "Landlord may enter the dwelling after reasonable notice to make repairs or show the unit. Emergencies may require entry without notice."),
              ("Community Rules", "Resident agrees to abide by the community rules including quiet hours, parking regulations, trash disposal and amenity use."),
              ("Early Termination", "Resident may terminate early by giving sixty days' written notice and paying a termination fee equal to two months' rent."),
              ("Renter's Insurance", "Resident is required to maintain renter's liability insurance throughout the lease term.")],
 "loan": [("Loan and Interest", "Lender agrees to make a loan to Borrower in the principal amount of {loan}. The loan shall bear interest at a fixed rate of {loanrate}% per annum, calculated on an Actual/360 basis."),
          ("Maturity and Amortization", "The loan matures {yrs} years from the Closing Date. Monthly payments shall be interest-only for the first {n} months and thereafter based on a 30-year amortization schedule."),
          ("Prepayment", "Borrower may prepay the loan in whole subject to yield maintenance or defeasance, except during the open period at the final ninety days before maturity."),
          ("Collateral", "The loan is secured by a first-lien mortgage on {name}, an assignment of leases and rents and a security interest in all personal property."),
          ("Financial Covenants", "Borrower shall maintain a minimum debt service coverage ratio of 1.25x and a maximum loan-to-value ratio of 65%, tested quarterly."),
          ("Reserves and Escrows", "Borrower shall fund monthly escrows for real estate taxes, insurance premiums and replacement reserves of $250 per unit annually."),
          ("Reporting Requirements", "Borrower shall deliver quarterly operating statements and rent rolls within forty-five days after quarter-end and audited annual financials within one hundred twenty days after year-end."),
          ("Cash Management", "Upon a Trigger Event, all revenues shall be deposited in a lender-controlled lockbox account."),
          ("Events of Default", "Events of default include failure to pay when due, breach of covenants, bankruptcy, transfer of the Property without consent and material misrepresentation."),
          ("Recourse Carve-Outs", "The loan is non-recourse to Borrower except for customary carve-outs including fraud, misappropriation, environmental indemnity and voluntary bankruptcy.")],
 "pma": [("Appointment", "Owner appoints Manager as the exclusive managing agent of {name}, and Manager accepts the appointment under the terms of this Agreement."),
         ("Term", "This Agreement has an initial term of one year and renews automatically for successive one-year terms unless terminated on thirty days' notice."),
         ("Management Fee", "Manager shall receive a monthly management fee equal to {pct3}% of Gross Collected Revenues, plus a construction supervision fee of 5% of capital project costs."),
         ("Duties of Manager", "Manager shall lease, market, operate and maintain the Property, collect rents, pay expenses, hire and supervise on-site personnel and maintain books and records."),
         ("Operating Account", "All receipts shall be deposited in a segregated operating account in Owner's name. Manager is authorized to disburse funds in accordance with the approved budget."),
         ("Budgets and Reporting", "Manager shall submit the annual operating and capital budget at least sixty days before each fiscal year and monthly financial reports by the fifteenth day of each month."),
         ("Spending Authority", "Manager may incur expenses not exceeding {amt} individually without Owner approval, except in an emergency threatening life or property."),
         ("Insurance and Indemnity", "Manager shall maintain workers' compensation, general liability and fidelity coverage and shall indemnify Owner against acts of gross negligence or willful misconduct."),
         ("Termination", "Owner may terminate this Agreement immediately for cause or upon sale of the Property. Manager shall deliver all records within ten days of termination.")],
 "vendor": [("Scope of Services", "Contractor shall furnish all labor, materials and equipment necessary to perform {scope} at {name} in accordance with the specifications attached hereto."),
            ("Term and Termination", "This Contract commences on the Effective Date for a term of {n} months and may be terminated by either party on thirty days' written notice."),
            ("Compensation", "Owner shall pay Contractor the monthly fee set forth in the Pricing Schedule within thirty days of receipt of an approved invoice."),
            ("Insurance", "Contractor shall maintain commercial general liability of $1,000,000, workers' compensation at statutory limits and automobile liability of $1,000,000."),
            ("Independent Contractor", "Contractor is an independent contractor and not an employee, agent or partner of Owner or its property manager."),
            ("Standard of Performance", "Services shall be performed in a professional and workmanlike manner by qualified personnel in compliance with applicable laws."),
            ("Indemnification", "Contractor shall indemnify, defend and hold harmless Owner and Manager from claims arising out of the performance of the services."),
            ("Service Levels", "Contractor shall respond to emergency calls within four hours and routine requests within two business days.")],
 "franchise": [("Grant of License", "Franchisor grants Franchisee a non-exclusive license to operate the {name} as a {flag} hotel at {address} for a term of {yrs} years."),
               ("Fees", "Franchisee shall pay a monthly royalty of {pct3}% of Gross Room Revenues, a program fee of 3% and reservation fees as set forth in the Fee Schedule."),
               ("Brand Standards", "Franchisee shall operate and maintain the Hotel in accordance with the Brand Standards Manual and complete the Product Improvement Plan by the dates specified."),
               ("Reservation System", "The Hotel shall participate in the central reservation system and loyalty program and honor all member rates and benefits."),
               ("Liquidated Damages", "If the Franchisee terminates early or the Franchisor terminates for cause, Franchisee shall pay liquidated damages equal to 36 months of royalty and program fees."),
               ("Quality Assurance", "Franchisor may conduct inspections and quality assurance audits with or without notice. Failure to achieve minimum scores may result in a default."),
               ("Transfer", "No sale or transfer of the Hotel may occur without Franchisor's consent, which shall not be unreasonably withheld, and payment of a transfer fee.")],
 "estoppel": [("Lease Documents", "The Lease dated as described above, together with any amendments listed, constitutes the entire agreement between Tenant and Landlord concerning the Premises at {name}."),
              ("Term and Rent", "The current term expires as stated in the Lease and monthly Base Rent presently payable is as shown above. No rent has been paid more than one month in advance."),
              ("Security Deposit", "Tenant has deposited the security deposit stated above and no other deposits are held by Landlord."),
              ("No Defaults", "To Tenant's knowledge, neither Tenant nor Landlord is in default under the Lease and no event has occurred that, with notice or lapse of time, would constitute a default."),
              ("Offsets and Claims", "Tenant has no defenses, offsets, counterclaims or credits against rent or other obligations under the Lease."),
              ("Improvements and Allowances", "All tenant improvements required to be completed by Landlord have been completed and all allowances have been paid in full."),
              ("Options", "Tenant has no option to purchase the Property and no right of first refusal or first offer except as expressly set forth in the Lease."),
              ("Reliance", "Tenant understands that Buyer and its lender will rely on this certificate in connection with the acquisition and financing of the Property.")],
 "title": [("Schedule A - Commitment", "Effective Date: {date}. Policy to be issued: ALTA Owner's Policy (2021). Proposed Insured: {buyer}. Amount of Insurance: {price}."),
           ("Schedule A - Estate or Interest", "Fee simple estate in the land described below is vested in {seller}."),
           ("Schedule B-I - Requirements", "Pay the full consideration to or for the account of the grantors. Record the deed from {seller} to {buyer}. Provide evidence of authority of signatories."),
           ("Schedule B-II - Exception", "Taxes and assessments for the year {yr} and subsequent years, a lien not yet due and payable."),
           ("Schedule B-II - Exception", "Easement in favor of the local electric utility recorded in Book {n}, Page {n}, Official Records of the county."),
           ("Schedule B-II - Exception", "Declaration of covenants, conditions and restrictions recorded as Instrument No. {n}{n}{n}, as amended."),
           ("Schedule B-II - Exception", "Rights of tenants, as tenants only, under unrecorded leases listed on the rent roll."),
           ("Schedule B-II - Exception", "Matters shown on survey prepared by {surveyor}, including encroachments, if any, along the boundary lines.")],
 "survey": [("Surveyor's Certificate", "To {buyer}, {title} and {lender}: this is to certify that this map or plat and the survey on which it is based were made in accordance with the 2021 Minimum Standard Detail Requirements for ALTA/NSPS Land Title Surveys."),
            ("Legal Description", "Being a tract of land situated in the county of record, beginning at an iron rod found at the intersection of the north line of {street} with the east line of the tract; thence N {n}° {n}' {n}\" E, a distance of {n}{n}.{n} feet to an iron rod set."),
            ("Survey Note 1", "The property contains {n}.{n} acres, more or less, and has direct access to {street}, a public right of way."),
            ("Survey Note 2", "Parking: {n}{n} regular spaces and {n} accessible spaces were counted on the surveyed property."),
            ("Survey Note 3", "No evidence of recent earth moving work, building construction or building additions was observed in the process of conducting the fieldwork."),
            ("Survey Note 4", "The surveyed property lies within Zone X (areas determined to be outside the 0.2% annual chance floodplain) per FIRM panel in effect."),
            ("Easements", "Utility easements as shown on the face of the survey are plotted to the extent described in the record documents provided in the title commitment.")],
}

# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------
def tenant_name(ctx):
    return f"{R.choice(TEN_A)} {R.choice(TEN_B.get(ctx['ptype'], TEN_B['Office']))}"

def T_rent_res(ctx, k, n):
    hdr = ["Unit", "Floorplan", "SF", "Resident", "Lease From", "Lease To", "Market", "Actual", "Status"]
    widths = [38, 62, 36, 106, 54, 54, 50, 50, 54]
    rows = []
    for i in range(n):
        u = 100 + k * n + i
        occ = R.random() < 0.93
        mr = ctx["rent"] * R.uniform(0.95, 1.08)
        s = rdate(dt.date(2023, 6, 1), dt.date(2026, 8, 1))
        rows.append([str(u), R.choice(["Studio", "1x1 A", "1x1 B", "2x1", "2x2 A", "2x2 B", "3x2"]),
                     num(ctx["avg_sf"] * R.uniform(0.8, 1.2)), person() if occ else "VACANT",
                     sdate(s) if occ else "", sdate(s + dt.timedelta(days=365)) if occ else "",
                     usd(mr), usd(mr * R.uniform(0.93, 1.02)) if occ else "$0",
                     R.choice(["Occupied"] * 8 + ["Notice"]) if occ else "Vacant"])
    return "Rent Roll with Lease Charges", hdr, rows, widths, (2, 6, 7)

def T_rent_com(ctx, k, n):
    hdr = ["Suite", "Tenant", "SF", "Lease From", "Lease To", "Rent PSF", "Monthly Base", "Rec./Mo.", "Type"]
    widths = [38, 132, 46, 54, 54, 44, 54, 44, 38]
    rows = []
    for i in range(n):
        sf = ctx["avg_sf"] * R.uniform(0.4, 1.6)
        psf = ctx["rent"] * R.uniform(0.85, 1.15)
        s = rdate(dt.date(2019, 1, 1), dt.date(2026, 6, 1))
        vac = R.random() < 0.08
        rows.append([f"{100 + (k * n + i) * 10 // 10 + 1}", "VACANT" if vac else tenant_name(ctx), num(sf),
                     "" if vac else sdate(s), "" if vac else sdate(s + dt.timedelta(days=365 * R.randint(3, 10))),
                     "" if vac else usd(psf, 2), "" if vac else usd(psf * sf / 12), "" if vac else usd(sf * R.uniform(0.5, 1.1) / 12),
                     "" if vac else R.choice(["NNN", "NNN", "MG", "FSG"])])
    return "Tenant Rent Roll", hdr, rows, widths, (2, 5, 6, 7)

LINES = ["Gross Potential Rent", "Loss to Lease", "Vacancy Loss", "Concessions", "Bad Debt", "Late Fees", "Utility Reimbursements",
         "Parking Income", "Application Fees", "Pet Rent", "Laundry Income", "Cable/Internet Revenue", "CAM Reimbursements",
         "Tax Reimbursements", "Insurance Reimbursements", "Percentage Rent", "Misc. Income", "Payroll - Management", "Payroll - Leasing",
         "Payroll - Maintenance", "Payroll Taxes & Benefits", "Repairs - Plumbing", "Repairs - HVAC", "Repairs - Electrical",
         "Repairs - Appliances", "Painting & Decorating", "Flooring", "Make-Ready / Turnover", "Landscaping Contract", "Snow Removal",
         "Janitorial", "Pest Control", "Trash Removal", "Elevator Contract", "Fire & Life Safety", "Security", "Electricity - Common",
         "Gas - Common", "Water & Sewer", "Telephone/Internet", "Advertising", "Resident Events", "Office Supplies", "Legal & Professional",
         "Accounting & Audit", "Licenses & Permits", "Management Fee", "Property Insurance", "Real Estate Taxes", "Asset Management Fee",
         "Replacement Reserves", "Roof Repairs", "Parking Lot Repairs", "Signage", "Tenant Improvements", "Leasing Commissions"]

def T_t12(ctx, k, n):
    mon = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    hdr = ["Account"] + mon + ["T-12"]
    widths = [92] + [31] * 12 + [40]
    rows = []
    n = min(n, len(LINES))
    start = (k * n) % len(LINES)
    for i in range(n):
        idx = (start + i) % len(LINES)
        base = ctx["rev"] / 12 * (R.uniform(0.01, 0.12) if idx > 16 else (R.uniform(0.01, 0.9) if idx else 1.0))
        vals = [base * R.uniform(0.93, 1.07) for _ in mon]
        rows.append([f"{4000 + idx * 10} {LINES[idx]}"] + [num(v) for v in vals] + [num(sum(vals))])
    return "Trailing 12-Month Operating Statement (Detail)", hdr, rows, widths, tuple(range(1, 14))

def T_budget(ctx, k, n):
    hdr = ["Account", "Prior Yr Actual", "Prior Yr Budget", "Current Budget", "Variance $", "Variance %", "Per Unit/SF"]
    widths = [150, 62, 62, 62, 56, 52, 60]
    rows = []
    for i in range(n):
        idx = (k * n + i) % len(LINES)
        a = ctx["rev"] * R.uniform(0.004, 0.09)
        b = a * R.uniform(0.92, 1.08)
        c = b * R.uniform(1.0, 1.07)
        rows.append([f"{5000 + idx * 10} {LINES[idx]}", usd(a), usd(b), usd(c), usd(c - a), f"{(c - a) / a * 100:.1f}%", usd(c / ctx['units'], 2)])
    return "Annual Operating Budget by Account", hdr, rows, widths, tuple(range(1, 7))

def T_sales(ctx, k, n):
    hdr = ["Comparable", "Location", "Sale Date", "Size", "Price", "$/Unit or SF", "Cap Rate", "Yr Built"]
    widths = [118, 76, 54, 52, 62, 56, 42, 44]
    rows = []
    for i in range(n):
        c = R.choice(CITIES)
        pr = ctx["price"] * R.uniform(0.4, 1.4)
        rows.append([f"{R.choice(NAME_WORDS)} {R.choice(SUFFIX[ctx['ptype']])}"[:26], f"{c[0]}, {c[1]}", sdate(rdate(dt.date(2022, 1, 1), dt.date(2026, 9, 1))),
                     num(ctx["units"] * R.uniform(0.5, 1.5)), usd(pr), usd(pr / (ctx['units'] if ctx['ptype'] in RES | {'Hotel', 'Self Storage'} else ctx['sf']), 0),
                     f"{R.uniform(5, 8.2):.2f}%", str(R.randint(1965, 2023))])
    return "Sales Comparison Data", hdr, rows, widths, (3, 4, 5, 6)

def T_rentcomps(ctx, k, n):
    hdr = ["Comparable", "Distance", "Yr Built", "Space Type", "Asking Rent", "Occupancy", "Concessions"]
    widths = [140, 52, 52, 80, 66, 56, 58]
    rows = [[f"{R.choice(NAME_WORDS)} {R.choice(SUFFIX[ctx['ptype']])}"[:30], f"{R.uniform(0.2, 5):.1f} mi", str(R.randint(1970, 2023)),
             R.choice(["Studio", "1BR", "2BR", "Suite", "Bay", "Inline", "Unit"]), usd(ctx["rent"] * R.uniform(0.85, 1.2), 2), f"{R.uniform(86, 98):.1f}%",
             R.choice(["None", "1 mo. free", "$500", "None"])] for _ in range(n)]
    return "Rent Comparables", hdr, rows, widths, (4, 5)

def T_closing(ctx, k, n):
    items = ["Purchase price", "Earnest money deposit", "Real estate tax proration", "Rent proration", "Security deposits assumed", "Prepaid rents",
             "Owner's title policy premium", "Lender's title policy premium", "Escrow fee", "Recording fees", "Transfer tax", "Survey",
             "Legal fees - Buyer", "Legal fees - Seller", "Broker commission", "Loan origination fee", "Lender legal", "Appraisal fee",
             "Environmental report", "Property condition report", "Tax escrow deposit", "Insurance escrow deposit", "Replacement reserve deposit",
             "Utility deposits", "Assumed vendor contracts credit", "Tenant improvement credit", "Courier / wire fees", "Municipal certificates"]
    hdr = ["Description", "Buyer Debit", "Buyer Credit", "Seller Debit", "Seller Credit"]
    widths = [204, 75, 75, 75, 75]
    rows = []
    for i in range(min(n, len(items))):
        v = ctx["price"] if i == 0 else ctx["price"] * R.uniform(0.0002, 0.01)
        rows.append([items[(k * 12 + i) % len(items)], usd(v) if i % 2 == 0 else "", usd(v) if i % 3 == 1 else "", usd(v) if i % 2 == 1 else "", usd(v) if i % 3 == 2 else ""])
    return "Settlement Statement - Itemized Charges", hdr, rows, widths, (1, 2, 3, 4)

def T_capex(ctx, k, n):
    projects = ["Roof replacement - Bldg {}", "Parking lot resurfacing", "HVAC replacement", "Lobby renovation", "Unit interior upgrades", "LED lighting retrofit",
                "Elevator modernization", "Exterior paint", "Amenity renovation", "Fire alarm panel upgrade", "ADA compliance", "Water heater replacement",
                "Signage / monument", "Storefront glazing", "Fence replacement", "Landscape / irrigation", "Security camera upgrade", "Sewer line repair", "Door hardware", "Pool resurfacing"]
    hdr = ["Project", "Category", "Start", "Completion", "Budget", "Spent to Date", "Status"]
    widths = [140, 70, 50, 56, 60, 62, 66]
    rows = []
    for i in range(n):
        b = R.randint(8, 900) * 1000
        rows.append([R.choice(projects).format(R.choice("ABCD")), R.choice(["Building", "Site", "Interior", "Life Safety", "Energy"]), sdate(rdate(dt.date(2023, 1, 1), dt.date(2026, 3, 1)))[:5] + "/" + str(R.randint(23, 26)),
                     R.choice(["Q1", "Q2", "Q3", "Q4"]) + " " + str(R.randint(2025, 2027)), usd(b), usd(b * R.uniform(0, 1.05)), R.choice(["Complete", "In progress", "Bidding", "Approved", "Deferred"])])
    return "Capital Project Schedule", hdr, rows, widths, (4, 5)

def T_claims(ctx, k, n):
    hdr = ["Claim No.", "Date of Loss", "Coverage", "Cause of Loss", "Status", "Paid", "Reserve"]
    widths = [76, 58, 62, 118, 52, 66, 72]
    rows = []
    for i in range(n):
        st = R.choice(["Closed", "Closed", "Closed", "Open"])
        rows.append([f"CL-{R.randint(2018, 2026)}-{R.randint(10000, 99999)}", sdate(rdate(dt.date(2019, 1, 1), dt.date(2026, 8, 1))), R.choice(["Property", "GL", "Water Dmg", "Liability"]),
                     R.choice(["Water damage - pipe burst", "Wind / hail", "Slip and fall", "Fire - kitchen", "Vandalism", "Roof leak", "Vehicle impact", "Theft"]), st,
                     usd(R.randint(500, 90000)), usd(R.randint(0, 40000)) if st == "Open" else "$0"])
    return "Claim Detail", hdr, rows, widths, (5, 6)

def T_str(ctx, k, n):
    hdr = ["Month", "Occ %", "ADR", "RevPAR", "Comp Occ", "Comp ADR", "Comp RevPAR", "MPI", "ARI", "RGI"]
    widths = [66] + [48] * 9
    rows = []
    y, m = 2024, 1
    for i in range(min(n, 36)):
        mm = (m - 1 + i + k * 12) % 12 + 1
        yy = y + (m - 1 + i + k * 12) // 12
        occ = R.uniform(52, 84); adr = ctx["rent"] * R.uniform(0.9, 1.15); co = occ * R.uniform(0.9, 1.1); ca = adr * R.uniform(0.9, 1.1)
        rows.append([f"{dt.date(yy, mm, 1):%b %Y}", f"{occ:.1f}", usd(adr, 2), usd(adr * occ / 100, 2), f"{co:.1f}", usd(ca, 2), usd(ca * co / 100, 2),
                     f"{occ / co * 100:.1f}", f"{adr / ca * 100:.1f}", f"{adr * occ / (ca * co) * 100:.1f}"])
    return "Monthly Performance vs. Competitive Set", hdr, rows, widths, tuple(range(1, 10))

def T_unitmix(ctx, k, n):
    sizes = ["5x5", "5x10", "10x10", "10x15", "10x20", "10x30", "5x5 CC", "5x10 CC", "10x10 CC", "10x15 CC", "Vehicle", "Wine locker"]
    hdr = ["Unit Size", "Type", "Total Units", "Occupied", "Occ %", "Street Rate", "Avg In-Place", "Vacant Units"]
    widths = [66, 80, 56, 56, 48, 66, 66, 66]
    rows = []
    for i in range(min(n, 36)):
        t = R.randint(6, 80); o = int(t * R.uniform(0.75, 0.99))
        rows.append([R.choice(sizes), R.choice(["Drive-up", "Climate controlled", "Interior", "Outdoor"]), str(t), str(o), f"{o / t * 100:.1f}%",
                     usd(ctx["rent"] * R.uniform(0.5, 2.2), 2), usd(ctx["rent"] * R.uniform(0.45, 2.0), 2), str(t - o)])
    return "Unit Mix and Rate Summary", hdr, rows, widths, tuple(range(2, 8))

def T_coverage(ctx, k, n):
    cov = ["Commercial Property", "General Liability", "Umbrella / Excess", "Business Income", "Flood", "Windstorm / Hail", "Terrorism (TRIA)",
           "Equipment Breakdown", "Ordinance & Law", "Workers' Compensation", "Cyber Liability", "Crime / Fidelity", "Pollution Legal Liability", "Employment Practices"]
    hdr = ["Coverage", "Carrier", "Policy No.", "Effective", "Expiration", "Limit", "Deductible"]
    widths = [106, 100, 76, 56, 56, 60, 50]
    rows = []
    for i in range(min(n, len(cov))):
        e = rdate(dt.date(2023, 1, 1), dt.date(2026, 6, 1))
        rows.append([cov[i], R.choice(INSURERS), f"{R.choice(['CPP', 'GL', 'UMB', 'BOP'])}{R.randint(1000000, 9999999)}", sdate(e), sdate(e + dt.timedelta(days=365)),
                     usd(R.choice([1, 2, 5, 10, 25, 50]) * 1000000), usd(R.choice([5, 10, 25, 50, 100]) * 1000)])
    return "Schedule of Coverages", hdr, rows, widths, (5, 6)

def T_tax(ctx, k, n):
    hdr = ["Parcel ID", "Description", "Land Value", "Improvements", "Assessed Total", "Mill Rate", "Tax Due", "Status"]
    widths = [70, 108, 58, 62, 62, 40, 56, 48]
    rows = []
    for i in range(n):
        tot = ctx["price"] / max(ctx["units"] // 3, 1) * R.uniform(0.2, 1.5)
        land = tot * R.uniform(0.15, 0.4)
        mill = R.uniform(18, 42)
        rows.append([f"{R.randint(10, 99)}-{R.randint(100, 999)}-{R.randint(1000, 9999)}", R.choice(["Land & Impr.", "Parcel Bldg A", "Parcel Bldg B", "Parking Lot", "Outparcel", "Common Area"]),
                     usd(land), usd(tot - land), usd(tot), f"{mill:.2f}", usd(tot * mill / 1000), R.choice(["Paid", "Paid", "Due", "Delinq."])])
    return "Parcel Detail", hdr, rows, widths, (2, 3, 4, 5, 6)

def T_findings(ctx, k, n):
    hdr = ["Item", "Location", "Observed Condition", "Recommended Action", "Priority", "Est. Cost"]
    widths = [90, 70, 116, 120, 42, 66]
    rows = []
    obs = [("Roof membrane", "Ponding / seams", "Re-seal and repair"), ("Asphalt paving", "Alligator cracking", "Mill and overlay"), ("Sprinkler heads", "Painted heads", "Replace"),
           ("HVAC unit", "Beyond useful life", "Replace RTU"), ("Stair treads", "Worn / loose", "Replace treads"), ("Sidewalk", "Trip hazards", "Grind / replace"),
           ("Water heater", "Corrosion", "Replace"), ("Window sealant", "Failed", "Re-caulk"), ("Handrail", "Loose", "Secure"), ("Fire extinguishers", "Expired tags", "Service"),
           ("Dumpster enclosure", "Damaged gate", "Repair")]
    for i in range(n):
        o = R.choice(obs)
        rows.append([o[0], R.choice(["Bldg A", "Bldg B", "Site", "Roof", "Mechanical", "Common"]), o[1], o[2], R.choice(["Immediate", "Year 1", "Year 2-5", "Reserve"]), usd(R.randint(1, 180) * 500)])
    return "Findings and Opinions of Cost", hdr, rows, widths, (5,)

def T_systems(ctx, k, n):
    sysn = ["Roof", "Paving", "HVAC", "Plumbing", "Electrical", "Elevators", "Fire/Life Safety", "Windows", "Siding/Facade", "Flooring", "Appliances", "Landscaping", "Pool/Amenity", "Signage", "Fencing"]
    hdr = ["System", "Age (yrs)", "EUL", "RUL", "Condition", "Immediate", "Reserve (10-yr)"]
    widths = [120, 52, 46, 46, 70, 80, 90]
    rows = []
    for i in range(min(n, 30)):
        eul = R.randint(10, 40); age = R.randint(1, eul)
        rows.append([sysn[i % len(sysn)] + ("" if i < len(sysn) else " (2)"), str(age), str(eul), str(eul - age), R.choice(["Good", "Fair", "Fair", "Poor"]), usd(R.randint(0, 40) * 1000), usd(R.randint(2, 280) * 1000)])
    return "Immediate Repairs and Replacement Reserve Schedule", hdr, rows, widths, (1, 2, 3, 5, 6)

def T_db(ctx, k, n):
    dbs = ["NPL (Superfund)", "CERCLIS / SEMS", "RCRA - Generators", "RCRA - TSD", "LUST", "UST", "State Hazardous Waste Sites", "Brownfields", "Engineering Controls", "Institutional Controls",
           "ERNS", "Drycleaner Facilities", "Solid Waste Landfills", "Voluntary Cleanup", "Historical Auto Stations"]
    hdr = ["Database", "Search Radius (mi)", "Sites Within Radius", "Subject Property?", "Further Evaluation"]
    widths = [170, 80, 90, 80, 84]
    rows = []
    for i in range(min(n, 30)):
        rows.append([dbs[i % len(dbs)], R.choice(["0.25", "0.5", "1.0"]), str(R.choice([0, 0, 0, 1, 2, 4, 7])), "No", R.choice(["None", "None", "None", "Reviewed - no action"])])
    return "Regulatory Database Search Results", hdr, rows, widths, (1, 2)

def T_license(ctx, k, n):
    regs = [("483.10", "Resident rights"), ("483.12", "Freedom from abuse"), ("483.24", "Quality of life"), ("483.25", "Quality of care"), ("483.35", "Nursing services"),
            ("483.45", "Pharmacy services"), ("483.60", "Food and nutrition"), ("483.70", "Administration"), ("483.80", "Infection control"), ("483.90", "Physical environment")]
    hdr = ["Tag", "Regulation", "Finding", "Severity", "Correction Due", "Status"]
    widths = [40, 130, 144, 56, 70, 64]
    rows = []
    for i in range(n):
        g = R.choice(regs)
        rows.append([f"F{R.randint(550, 950)}", g[0] + " " + g[1], R.choice(["No deficiency", "Documentation gap", "Staffing ratio", "Medication log", "Cleanliness", "Care plan review"]),
                     R.choice(["A", "B", "C", "D", "E"]), sdate(rdate(dt.date(2024, 1, 1), dt.date(2026, 10, 1))), R.choice(["Corrected", "Corrected", "POC accepted", "Pending"])])
    return "Statement of Deficiencies", hdr, rows, widths, ()

TABLES = dict(rent_res=T_rent_res, rent_com=T_rent_com, t12=T_t12, budget=T_budget, sales=T_sales, rentcomps=T_rentcomps, closing=T_closing, capex=T_capex,
              claims=T_claims, str=T_str, unitmix=T_unitmix, coverage=T_coverage, tax=T_tax, findings=T_findings, systems=T_systems, db=T_db, license=T_license)

# --------------------------------------------------------------------------
# Document-type specs
# --------------------------------------------------------------------------
ALL = set(PTYPES)
def rent_kind(ctx):
    return "rent_res" if ctx["ptype"] in RES else "rent_com"

# issuer role, category, applicable types, weight (recurrence), body section list, closer, cover kv fn
DTS = {}
def reg(name, cat, applies, issuer, weight, body, closer, kv, intro=None):
    DTS[name] = dict(name=name, cat=cat, applies=applies, issuer=issuer, weight=weight, body=body, closer=closer, kv=kv, intro=intro)

def kvf(*pairs):
    return lambda c, d: [(a, fmt(b, {**c, **d}) if isinstance(b, str) else b) for a, b in pairs]

STD = lambda c, d: dict(close=dstr(d["date"] + dt.timedelta(days=45)), dep=usd(round(c["price"] * 0.02, -3)), date=dstr(d["date"]), loanrate=f"{c['rate_']:.2f}",
                        price=usd(c["price"]), loan=usd(c["loan"]), rentu=usd(c["rent"]), avgsf=num(c["avg_sf"]), scope=d.get("scope", "building services"),
                        title=d.get("title_co", ""), surveyor=d.get("surveyor", ""), street=c["street"].split(" ", 1)[1])

reg("Offering Memorandum", "Acquisition", ALL, "broker", 1, [("narr", ["inv", "market"]), ("table", "sales"), ("narr", ["building", "fin"]), ("table", "rentcomps"), ("narr", ["ops", "market"])], "disclaimer",
    kvf(("Property", "{name}"), ("Location", "{address}"), ("Property Type", "{ptype}"), ("Size", "{size}"), ("Year Built", "{year}"), ("Offering", "Unpriced - Offers Due {date}")))
reg("Purchase and Sale Agreement", "Acquisition", ALL, "law", 1, [("clauses", "psa")], "sig",
    kvf(("Seller", "{seller}"), ("Buyer", "{buyer}"), ("Property", "{name}, {address}"), ("Purchase Price", "{price}"), ("Effective Date", "{date}")))
reg("Closing Statement", "Acquisition", ALL, "title", 1, [("table", "closing"), ("narr", ["fin"])], "sig",
    kvf(("Property", "{name}"), ("Settlement Date", "{date}"), ("Buyer", "{buyer}"), ("Seller", "{seller}"), ("Sale Price", "{price}")))
reg("Title Commitment", "Acquisition", ALL, "title", 1, [("clauses", "title")], "disclaimer",
    kvf(("Commitment No.", "TC-{n}{n}{n}{n}"), ("Property", "{name}, {address}"), ("Proposed Insured", "{buyer}"), ("Effective Date", "{date}")))
reg("ALTA Survey", "Acquisition", ALL, "surveyor", 0.8, [("clauses", "survey"), ("narr", ["site"])], "cert",
    kvf(("Project", "{name}"), ("Address", "{address}"), ("Client", "{buyer}"), ("Field Work Date", "{date}")))
reg("Appraisal Report", "Due Diligence", ALL, "appraiser", 1.2, [("narr", ["market", "site"]), ("narr", ["building"]), ("table", "sales"), ("narr", ["fin"]), ("table", "rentcomps")], "cert",
    kvf(("Subject Property", "{name}"), ("Address", "{address}"), ("Property Rights Appraised", "Fee Simple"), ("Effective Date of Value", "{date}"), ("Market Value Conclusion", "{price}")))
reg("Phase I Environmental Site Assessment", "Due Diligence", ALL, "env", 1, [("narr", ["site", "env"]), ("table", "db"), ("narr", ["env"])], "cert",
    kvf(("Site", "{name}"), ("Address", "{address}"), ("Prepared For", "{buyer}"), ("Report Date", "{date}"), ("Standard", "ASTM E1527-21")))
reg("Property Condition Assessment", "Due Diligence", ALL, "eng", 1, [("narr", ["building", "cond"]), ("table", "systems"), ("table", "findings"), ("narr", ["cond"])], "cert",
    kvf(("Property", "{name}"), ("Address", "{address}"), ("Site Visit Date", "{date}"), ("Client", "{buyer}"), ("Immediate Repairs", "{amt}")))
reg("Zoning Compliance Letter", "Due Diligence", ALL, "env", 0.5, [("narr", ["reg"]), ("narr", ["site", "reg"])], "sig",
    kvf(("Subject", "Zoning verification for {name}"), ("Address", "{address}"), ("Date", "{date}"), ("Zoning District", "{n}-{n}")))
reg("Commercial Lease Agreement", "Leasing", COM, "law", 2.2, [("clauses", "lease"), ("table", "capex")], "sig",
    kvf(("Landlord", "{owner}"), ("Tenant", "{tenant}"), ("Premises", "Suite {n}{n}0, {name}"), ("Lease Date", "{date}"), ("Term", "{yrs} years")), intro=None)
reg("Lease Amendment", "Leasing", COM, "law", 1.6, [("clauses", "lease")], "sig",
    kvf(("Landlord", "{owner}"), ("Tenant", "{tenant}"), ("Premises", "Suite {n}{n}0, {name}"), ("Amendment Date", "{date}"), ("Amendment No.", "{n}")))
reg("Estoppel Certificate", "Leasing", COM, "tenant", 1.6, [("clauses", "estoppel"), ("clauses", "estoppel")], "sig",
    kvf(("Tenant", "{tenant}"), ("Premises", "Suite {n}{n}0, {name}"), ("Landlord", "{owner}"), ("Date", "{date}"), ("Addressed To", "{buyer} and {lender}")))
reg("Residential Lease Agreement", "Leasing", RES, "law", 2.2, [("clauses", "reslease")], "sig",
    kvf(("Landlord", "{owner}"), ("Resident", "{resident}"), ("Dwelling", "Unit {n}{n}{n}, {name}"), ("Lease Date", "{date}"), ("Monthly Rent", "{rentu}")))
reg("Rent Roll", "Leasing", RES | COM, "pm", 3.2, [("table", "RENT")], "summary",
    kvf(("Property", "{name}"), ("Report", "Rent Roll as of {date}"), ("Address", "{address}"), ("Total Size", "{size}"), ("Prepared By", "{manager}")))
reg("Storage Unit Mix and Rate Report", "Leasing", {"Self Storage"}, "pm", 3.0, [("table", "unitmix"), ("narr", ["ops"])], "summary",
    kvf(("Facility", "{name}"), ("Report Date", "{date}"), ("Address", "{address}"), ("Total Units", "{size}")))
reg("STR Benchmark Report", "Operations", {"Hotel"}, "pm", 3.0, [("table", "str"), ("narr", ["ops", "market"])], "summary",
    kvf(("Hotel", "{name}"), ("Report Period", "Through {date}"), ("Brand", "{flag}"), ("Rooms", "{size}")))
reg("Franchise Agreement", "Operations", {"Hotel"}, "law", 1, [("clauses", "franchise")], "sig",
    kvf(("Hotel", "{name}"), ("Franchisor", "{flag} Hotels Inc."), ("Franchisee", "{owner}"), ("Agreement Date", "{date}"), ("Term", "{yrs} years")))
reg("State Licensing Survey Report", "Operations", {"Senior Housing"}, "env", 2.0, [("table", "license"), ("narr", ["ops", "reg"])], "sig",
    kvf(("Facility", "{name}"), ("License Type", "Assisted Living / Memory Care"), ("Survey Date", "{date}"), ("Address", "{address}")))
reg("T-12 Operating Statement", "Financial", ALL, "pm", 3.0, [("table", "t12"), ("narr", ["fin", "ops"])], "summary",
    kvf(("Property", "{name}"), ("Period Ending", "{date}"), ("Basis", "Accrual - Trailing 12 Months"), ("Prepared By", "{manager}"), ("Size", "{size}")))
reg("Annual Operating Budget", "Financial", ALL, "pm", 1.4, [("table", "budget"), ("narr", ["fin", "ops"])], "summary",
    kvf(("Property", "{name}"), ("Fiscal Year", "{yr}"), ("Submitted By", "{manager}"), ("Submitted", "{date}")))
reg("Quarterly Investor Report", "Financial", ALL, "am", 2.6, [("narr", ["inv", "ops"]), ("table", "capex"), ("narr", ["fin", "market"]), ("table", "budget")], "disclaimer",
    kvf(("Investment", "{name}"), ("Quarter", "{q} {yr}"), ("Report Date", "{date}"), ("Sponsor", "{buyer}"), ("Occupancy", "{pct2}%")))
reg("Property Tax Bill", "Financial", ALL, "county", 2.0, [("table", "tax"), ("narr", ["reg", "fin"])], "summary",
    kvf(("Property", "{name}"), ("Tax Year", "{yr}"), ("Bill Date", "{date}"), ("Owner of Record", "{owner}"), ("Site", "{address}")))
reg("Capital Improvement Plan", "Financial", ALL, "am", 1.2, [("table", "capex"), ("narr", ["cond", "inv"])], "summary",
    kvf(("Property", "{name}"), ("Plan Date", "{date}"), ("Prepared For", "{buyer}"), ("Total Plan Budget", "{amt}")))
reg("Loan Agreement", "Debt", ALL, "law", 1, [("clauses", "loan")], "sig",
    kvf(("Borrower", "{owner}"), ("Lender", "{lender}"), ("Collateral", "{name}"), ("Loan Amount", "{loan}"), ("Rate", "{loanrate}% Fixed"), ("Closing Date", "{date}")))
reg("Certificate of Insurance", "Insurance", ALL, "insbrk", 2.0, [("table", "coverage"), ("clauses", "pma")], "disclaimer",
    kvf(("Insured", "{owner}"), ("Location Covered", "{name}, {address}"), ("Certificate Date", "{date}"), ("Mortgagee", "{lender}")))
reg("Insurance Loss Run", "Insurance", ALL, "insbrk", 1.4, [("table", "claims")], "summary",
    kvf(("Insured", "{owner}"), ("Location", "{name}"), ("Valued As Of", "{date}"), ("Policy Years", "{yr} - current")))
reg("Property Management Agreement", "Operations", ALL, "law", 1, [("clauses", "pma")], "sig",
    kvf(("Owner", "{owner}"), ("Manager", "{manager}"), ("Property", "{name}, {address}"), ("Agreement Date", "{date}")))
reg("Vendor Service Contract", "Operations", ALL, "vendor", 2.0, [("clauses", "vendor")], "sig",
    kvf(("Owner", "{owner}"), ("Contractor", "{vendor}"), ("Services", "{scope}"), ("Property", "{name}"), ("Effective Date", "{date}")))

# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
FONTS = {"Helvetica": ("Helvetica", "Helvetica-Bold"), "Times": ("Times-Roman", "Times-Bold"), "Courier": ("Courier", "Courier-Bold")}

class Doc:
    def __init__(self, ctx, spec, date, pages):
        self.ctx, self.spec, self.date, self.pages = ctx, spec, date, pages
        self.font = R.choices(list(FONTS), [6, 3, 1])[0]
        self.accent = colors.HexColor(R.choice(ACCENTS))
        self.hdr_mode = R.choices(["full", "addr", "none"], [7, 2, 1])[0]
        self.clause_no = 0
        self.table_k = {}
        self.vendor, self.scope = R.choice(VENDORS)
        self.tenant = tenant_name(ctx) if ctx["ptype"] in COM else ""
        self.resident = person()
        self.issuer = self.pick_issuer(spec["issuer"])
        self.extra = dict(vendor=self.vendor, scope=self.scope, tenant=self.tenant, resident=self.resident)
        self.extra.update(title_co=R.choice(TITLECOS), surveyor=R.choice(SURVEYORS))
        self.ref = f"{R.choice('ABCDEFGHJKLMNPRSTW')}{R.choice('ABCDEFGHJKLMNPRSTW')}-{R.randint(10000, 99999)}"
        r, b = FONTS[self.font]
        S = lambda **k: ParagraphStyle("x", **k)
        self.st = dict(body=S(fontName=r, fontSize=9, leading=12, spaceAfter=5, alignment=4),
                       h1=S(fontName=b, fontSize=15, leading=19, spaceAfter=6, textColor=self.accent),
                       h2=S(fontName=b, fontSize=10.5, leading=13, spaceBefore=5, spaceAfter=3, textColor=self.accent),
                       title=S(fontName=b, fontSize=21, leading=25, spaceAfter=4, textColor=self.accent),
                       sub=S(fontName=r, fontSize=10, leading=13, spaceAfter=10, textColor=colors.HexColor("#444444")),
                       small=S(fontName=r, fontSize=7.5, leading=10, textColor=colors.HexColor("#555555")),
                       cl=S(fontName=r, fontSize=9, leading=12, spaceAfter=4, alignment=4, leftIndent=0))

    def pick_issuer(self, role):
        c = self.ctx
        return dict(broker=R.choice(BROKERS), law=R.choice(LAWFIRMS), title=R.choice(TITLECOS), surveyor=R.choice(SURVEYORS),
                    appraiser=R.choice(APPRAISERS), env=R.choice(ENVCOS), eng=R.choice(ENGCOS), tenant=c["owner"], pm=c["manager"], am=c["buyer"],
                    county=f"{c['city']} County Treasurer", insbrk=R.choice(INSBRK), vendor=self.vendor_name() if role == "vendor" else "").get(role, c["manager"])

    def vendor_name(self):
        return self.vendor

    def info(self):
        d = dict(self.ctx); d.update(STD(self.ctx, {"date": self.date, **self.extra}))
        d.update(self.extra); d.setdefault("seller", self.ctx["seller"]); d["title"] = self.extra["title_co"]
        return d

    # ---- flowable builders ----
    def P(self, t, s="body"):
        return Paragraph(esc(t).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>"), self.st[s])

    def tbl(self, header, rows, widths, right=(), fs=7.3):
        r, b = FONTS[self.font]
        def fit(t, w):
            t = str(t)
            while stringWidth(t, r, fs) > w - 4 and len(t) > 1:
                t = t[:-1]
            return t
        data = [[fit(h, w) for h, w in zip(header, widths)]] + [[fit(c, w) for c, w in zip(row, widths)] for row in rows]
        t = Table(data, colWidths=widths, rowHeights=[fs + 5.6] * len(data))
        st = [("FONTNAME", (0, 0), (-1, 0), b), ("FONTNAME", (0, 1), (-1, -1), r if self.font != "Courier" else r), ("FONTSIZE", (0, 0), (-1, -1), fs),
              ("BACKGROUND", (0, 0), (-1, 0), self.accent), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#aaaaaa")),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]
        for c in right:
            st.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
        t.setStyle(TableStyle(st))
        return t

    def kv(self, pairs):
        r, b = FONTS[self.font]
        data = [[Paragraph(f"<b>{esc(a)}</b>", self.st["body"]), Paragraph(esc(v), self.st["body"])] for a, v in pairs]
        t = Table(data, colWidths=[140, FW - 140])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#bbbbbb")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        return t

    def narr_page(self, themes):
        info, out = self.info(), []
        info["rentu"] = usd(self.ctx["rent"])
        for t in themes * 3:
            out.append(self.P(R.choice(HEADS[t]), "h2"))
            sents = NARR[t] + FLAVOR[self.ctx["ptype"]] * (1 if t in ("building", "fin", "market", "ops", "inv") else 0)
            for _ in range(2):
                out.append(self.P(" ".join(fmt(s, info) for s in R.sample(sents, min(len(sents), R.randint(4, 6))))))
        return out

    def clause_page(self, bank):
        info, out = self.info(), []
        items = BANKS[bank]
        for _ in range(7):
            head, text = items[self.clause_no % len(items)]
            self.clause_no += 1
            more = " ".join(fmt(s, info) for s in R.sample(LEGAL_FILL, 2))
            out.append(self.P(f"<b>{self.clause_no}. {esc(head)}.</b> {fmt(text, info)} {more}", "cl"))
        return out

    def table_page(self, kind, first=False):
        if kind == "RENT":
            kind = rent_kind(self.ctx)
        k = self.table_k.get(kind, 0); self.table_k[kind] = k + 1
        fs = 6.2 if kind == "t12" else 7.3
        n = int((330 if first else 560) / (fs + 5.6)) - R.randint(0, 3)
        title, hdr, rows, widths, right = TABLES[kind](self.ctx, k, n)
        return [self.P(title, "h2"), self.tbl(hdr, rows, widths, right, fs), Spacer(1, 6),
                self.P(f"Report generated {sdate(self.date)}. Figures are unaudited and subject to change.", "small")]

    def section(self, tok, first=False):
        kind, arg = tok
        if kind == "table":
            return self.table_page(arg, first)
        return {"narr": self.narr_page, "clauses": self.clause_page}[kind](arg)

    def closer_page(self):
        s, info, out = self.spec["closer"], self.info(), []
        c = self.ctx
        if s == "sig":
            out += [self.P("Signatures", "h1"), self.P("IN WITNESS WHEREOF, the parties have executed this instrument as of the date first written above.")]
            for who in [c["seller"] if "Purchase" in self.spec["name"] else c["owner"], self.tenant or self.resident or c["buyer"]]:
                out += [Spacer(1, 22), self.P("_" * 46, "body"), self.P(f"{who}", "body"), self.P(f"By: {person()}    Title: {R.choice(['Manager', 'Authorized Signatory', 'Managing Member', 'President'])}    Date: {sdate(self.date)}", "small")]
            out += [Spacer(1, 14), self.P("Exhibit A - Property", "h2"), self.P(f"{c['name']}, {c['address']}. Parcel containing approximately {R.randint(1, 30)}.{R.randint(10, 99)} acres, together with all improvements thereon.")]
        elif s == "cert":
            out += [self.P("Certification", "h1"), self.P(f"I certify that, to the best of my knowledge and belief, the statements of fact contained in this report are true and correct and that I have no present or prospective interest in {c['name']} and no personal interest with respect to the parties involved.")]
            out += [self.P(f"The analyses, opinions and conclusions are limited only by the reported assumptions and limiting conditions. The inspection of the property was performed on {dstr(self.date - dt.timedelta(days=R.randint(5, 30)))}."),
                    Spacer(1, 24), self.P("_" * 40), self.P(f"{person()}, {R.choice(['MAI', 'PE', 'CPG', 'RPLS', 'Senior Associate'])}"), self.P(f"{self.issuer}", "small")]
        elif s == "summary":
            out += [self.P("Summary and Notes", "h1")] + self.narr_page(["fin", "ops"])[:6]
        else:
            out += [self.P("Disclaimer and Confidentiality", "h1")]
            for _ in range(6):
                out.append(self.P(" ".join(fmt(x, info) for x in R.sample(LEGAL_FILL, 4)) + f" This document relates solely to {c['name']} and has been prepared for the use of the recipient only; it may not be reproduced or distributed."))
        return out

    def render(self, path):
        s, n = self.spec, self.pages
        cv = canvas.Canvas(path, pagesize=letter, pageCompression=1)
        cv.setTitle("Scan"); cv.setAuthor(""); cv.setCreator("Scan"); cv.setProducer("Scan")
        body = s["body"]
        for i in range(n):
            if i == 0:
                fl = self.cover_flow()
                first = body[0]
                fl += self.section(first, True)
            elif i == n - 1 and n >= 2 and s["closer"] and not (n > 2 and R.random() < 0.2):
                fl = self.closer_page()
            else:
                fl = self.section(body[(i - 1) % len(body)])
            self.page_chrome(cv, i)
            fr = Frame(MX, BOT, FW, FH, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
            for f in fl:
                try:
                    if not fr.add(f, cv):
                        break
                except LayoutError:
                    continue
            cv.showPage()
        cv.save()

    def cover_flow(self):
        s, c, info = self.spec, self.ctx, self.info()
        pairs = s["kv"](c, info)
        out = [Spacer(1, 4), self.P(s["name"].upper(), "title"), self.P(f"{c['name']}  |  {c['city']}, {c['state']}", "sub"), self.kv(pairs), Spacer(1, 10)]
        return out

    def page_chrome(self, cv, i):
        r, b = FONTS[self.font]
        c = self.ctx
        grey = colors.HexColor("#666666")
        if i == 0:
            cv.setFillColor(self.accent); cv.rect(0, H - 40, W, 40, stroke=0, fill=1)
            cv.setFillColor(colors.white); cv.setFont(b, 12); cv.drawString(MX, H - 26, self.issuer)
            cv.setFont(r, 8); cv.drawRightString(W - MX, H - 26, f"Ref. {self.ref}  •  {dstr(self.date)}")
        else:
            cv.setFillColor(grey); cv.setFont(r, 7.5)
            tail = {"full": f"{c['name']}", "addr": c["street"], "none": f"Ref. {self.ref}"}[self.hdr_mode]
            cv.drawString(MX, H - 40, f"{self.spec['name']}  —  {tail}")
            cv.drawRightString(W - MX, H - 40, f"Page {i + 1} of {self.pages}")
            cv.setStrokeColor(self.accent); cv.setLineWidth(1.2); cv.line(MX, H - 45, W - MX, H - 45)
        cv.setFillColor(colors.HexColor("#999999")); cv.setFont(r, 6.5)
        cv.drawCentredString(W / 2, 30, "FICTITIOUS SAMPLE DOCUMENT — all names, figures and entities are invented for classroom training use only")

# --------------------------------------------------------------------------
# Plan + build
# --------------------------------------------------------------------------
LOOSE_NAMES = [lambda d, n: f"scan_{d:%Y%m%d}_{R.randint(700, 1900):04d}.pdf", lambda d, n: f"IMG_{R.randint(1000, 9999)}.pdf",
               lambda d, n: f"Document ({R.randint(1, 400)}).pdf", lambda d, n: f"doc_{R.randrange(16**6):06x}.pdf",
               lambda d, n: f"New Scan {R.randint(1, 900)}.pdf", lambda d, n: f"attachment_{R.randint(1, 9999)}.pdf",
               lambda d, n: f"final_FINAL_v{R.randint(1, 9)}.pdf", lambda d, n: f"untitled{R.randint(1, 999)}.pdf",
               lambda d, n: f"download ({R.randint(1, 300)}).pdf", lambda d, n: f"{d:%Y%m%d}_{R.randint(1000, 9999)}.pdf",
               lambda d, n: f"Scan{R.randint(1, 9999)} - Copy.pdf", lambda d, n: f"file{R.randint(10000, 99999)}.pdf",
               lambda d, n: f"CCE{d:%m%d%Y}.pdf", lambda d, n: f"Doc{R.randint(1, 99)}_{R.randint(1, 99)}.pdf"]

def doc_date(prop, spec):
    acq, end = prop["acq"], dt.date(2026, 10, 15)
    if spec["cat"] in ("Acquisition", "Due Diligence") or spec["name"] in ("Loan Agreement", "Property Management Agreement"):
        return acq - dt.timedelta(days=R.randint(0, 120)) if spec["cat"] == "Due Diligence" else acq - dt.timedelta(days=R.randint(0, 45))
    return rdate(acq, end)

def plan(props, total):
    docs = []
    per = {}
    for p in props:
        ok = [n for n, s in DTS.items() if p["ptype"] in s["applies"]]
        k = min(len(ok), R.randint(5, 8))
        per[p["pid"]] = R.sample(ok, k)
        docs += [(p, t) for t in per[p["pid"]]]
    while len(docs) > total:
        docs.pop(R.randrange(len(docs)))
    while len(docs) < total:
        p = R.choice(props)
        types = per[p["pid"]]
        docs.append((p, R.choices(types, [DTS[t]["weight"] for t in types])[0]))
    R.shuffle(docs)
    return docs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261102)
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--properties", type=int, default=130)
    ap.add_argument("--out", default=os.path.join(HERE, "documents"))
    a = ap.parse_args()
    R.seed(a.seed)
    key_dir = os.path.join(HERE, "instructor_answer_key")
    shutil.rmtree(a.out, ignore_errors=True); os.makedirs(a.out); os.makedirs(key_dir, exist_ok=True)
    props = make_properties(a.properties)
    docs = plan(props, a.count)
    used, rows = set(), []
    for i, (p, t) in enumerate(docs, 1):
        spec = DTS[t]
        d = doc_date(p, spec)
        pages = R.randint(1, 15)
        while True:
            fn = R.choice(LOOSE_NAMES)(d, i)
            if fn.lower() not in used:
                used.add(fn.lower()); break
        D = Doc(p, spec, d, pages)
        D.render(os.path.join(a.out, fn))
        folder = f"{p['ptype']}/{p['name']}/{spec['cat']}"
        rows.append(dict(filename=fn, property_id=p["pid"], property_name=p["name"], property_type=p["ptype"], address=p["address"],
                         document_type=t, category=spec["cat"], document_date=d.isoformat(), pages=pages, issuer=D.issuer,
                         suggested_folder=folder, suggested_filename=f"{d:%Y-%m-%d} - {t}.pdf"))
        if i % 100 == 0:
            print(f"  {i}/{len(docs)} documents written", flush=True)
    with open(os.path.join(key_dir, "answer_key.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(sorted(rows, key=lambda r: (r["property_type"], r["property_name"], r["document_date"])))
    with open(os.path.join(key_dir, "properties.csv"), "w", newline="") as f:
        cols = ["pid", "name", "ptype", "address", "year", "size", "price", "acq", "owner", "seller", "buyer", "lender", "manager"]
        w = csv.writer(f); w.writerow(["property_id", "property_name", "property_type", "address", "year_built", "size", "purchase_price", "acquisition_date",
                                       "owner_entity", "seller", "buyer", "lender", "property_manager"])
        for p in props:
            w.writerow([p[c] for c in cols])
    print("done:", len(rows), "documents,", len(props), "properties")

if __name__ == "__main__":
    main()
