#  Copyright (c) 2025.  VesselHarbor
#
#  ____   ____                          .__    ___ ___             ___.
#  \   \ /   /____   ______ ______ ____ |  |  /   |   \_____ ______\_ |__   ___________
#   \   Y   // __ \ /  ___//  ___// __ \|  | /    ~    \__  \\_  __ \ __ \ /  _ \_  __ \
#    \     /\  ___/ \___ \ \___ \\  ___/|  |_\    Y    // __ \|  | \/ \_\ (  <_> )  | \/
#     \___/  \___  >____  >____  >\___  >____/\___|_  /(____  /__|  |___  /\____/|__|
#                \/     \/     \/     \/            \/      \/          \/
#
#
#  MIT License
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.
#

from typing import Optional
import random
import string

# --- Listes de qualificatifs liés à l’astronomie ---------------------------------

adjectives = [
    # Appearance / luminosity
    "bright", "radiant", "brilliant", "glowing", "luminous", "shimmering",
    "gleaming", "sparkling", "glistening", "iridescent", "silver", "golden",
    "spectral", "chromatic", "colorful",

    # Scale & structure
    "massive", "giant", "supergiant", "hypergiant", "colossal", "gargantuan",
    "compact", "dense", "dwarf", "subdwarf", "rocky", "gaseous", "icy",
    "metallic", "carbonaceous", "silicaceous", "ringed", "multiringed",
    "spiral", "barred", "elliptical", "spherical",

    # Spatial orientation & motion
    "orbital", "circumstellar", "circumplanetary", "circumlunar", "sidereal",
    "axial", "polar", "equatorial", "zenithal", "ecliptic", "perigean",
    "apogean", "perihelial", "aphelian", "retrograde", "prograde",
    "transient", "variable", "periodic",

    # Cosmic nature
    "stellar", "protostellar", "celestial", "solar", "lunar", "planetary",
    "exoplanetary", "extrasolar", "galactic", "circumgalactic", "interstellar",
    "intergalactic", "cosmic", "nebular", "molecular", "astral",

    # Energy & phenomena
    "magnetized", "pulsating", "pulsatory", "flaring", "eruptive", "volatile",
    "quiescent", "distant", "faraway", "nearby", "ancient", "primordial",
    "primeval", "young", "nascent", "relativistic", "gravitational", "tidal",
    "lensing", "hydrodynamic", "baryonic", "dark", "shadowy",

    # Spectral & radiation
    "infrared", "ultraviolet", "xray", "gamma", "radio", "photonic",

    # Miscellaneous resonance
    "resonant", "echoing",
]

adverbs = [
    "fluorescently", "universally", "multiversally", "hyperspatially", "astronomically",
    "magnetically", "pulsationally", "flarefully", "radiatively", "photometrically",
    "luminally", "tachyonically", "vastly", "immensely", "infinitely", "profoundly",
    "utterly", "deeply", "totally", "epochally", "aeonically", "eternally",
    "momentarily", "instantaneously", "annually", "daily", "newly", "surely",
    "truly", "really", "locally", "globally",

    # --- Luminosity & brilliance ------------------------------------------------
    "scintillantly", "coruscantly", "effulgently", "luminescently", "phosphorescently",
    "aurorally", "beamingly", "glintingly", "glimmeringly", "twinklingly", "starrily",

    # --- Spatial / directional --------------------------------------------------
    "radially", "tangentially", "azimuthally", "zenithward", "nadirward", "heliocentrically",
    "geocentrically", "barycentrically", "apogeeward", "perigeeward", "sunward", "earthward",
    "starward", "planetward", "galaxyward", "spherically",

    # --- Energy & physical processes -------------------------------------------
    "magnetohydrodynamically", "turbulently", "explosively", "ablatively", "convectively",
    "adiabatically", "cataclysmically", "thermally", "hyperbolically", "elliptically",
    "parabolically", "circularly", "inertially", "ballistically", "ionically", "plasmatically",
    "quantumly", "relativistically", "nuclearly", "fusionally", "fissionally", "radiogenically",
    "isotropically", "anisotropically", "dynamically", "kinematically", "hydrodynamically",

    # --- Temporal & frequency ---------------------------------------------------
    "oscillationally", "ephemerally", "intermittently", "diurnally", "nocturnally",
    "seasonally", "quasiperiodically", "perpetually", "timelessly", "synchronously",
    "asynchronously", "sequentially", "continuously",

    # --- Degree & intensity -----------------------------------------------------
    "marginally", "moderately", "substantially", "enormously", "tremendously", "titanically",
    "colossally", "infinitesimally", "appreciably", "detectably", "imperceptibly",
    "overwhelmingly", "minutely", "negligibly", "significantly", "conspicuously",
    "vividly",  "starkly", "emphatically", "drastically", "radically", "acutely",

    # --- Probability & epistemic -----------------------------------------------
    "ostensibly", "evidently", "plausibly", "conceivably", "arguably", "hypothetically",
    "theoretically", "empirically", "observationally",

    # --- Position & motion ------------------------------------------------------
    "inwardly", "outwardly", "upwardly", "downwardly", "eastward", "westward",
    "northward", "southward", "spaceward", "homeward", "afar", "yonder", "forth",
    "backwardly", "centrally", "peripherally", "sidelong", "laterally", "axially",
    "ecliptically", "polymetrically", "speculatively", "computationally",
    "algorithmically", "numerically", "analytically", "systematically",
    "methodically", "instrumentally",
]



# --- Objets astronomiques (toujours en minuscules) ------------------------------

names = [
    # Stars
    "sirius", "betelgeuse", "rigel", "vega", "altair", "deneb", "aldebaran",
    "antares", "polaris", "capella", "arcturus", "spica", "canopus", "acrux",
    "hadar", "achernar", "algol", "mirach", "sun", "procyon", "regulus",
    "castor", "pollux", "denebola", "fomalhaut", "mintaka", "alnilam",
    "alnitak", "saiph", "bellatrix", "menkar", "menkalinan", "mirfak",
    "mizar", "alkaid", "dubhe", "merak", "phecda", "megrez", "alioth",
    "scheat", "markab", "sadalmelik", "sadalsuud", "rukbat", "alnair",
    "alphard", "mirzam", "shedir", "tarazed", "gacrux", "nunki", "ascella",
    "kraz",
    # Planets & dwarf planets
    "mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus",
    "neptune", "pluto", "haumea", "makemake", "eris", "ceres",
    # Moons & natural satellites
    "moon", "luna", "phobos", "deimos", "io", "europa", "ganymede",
    "callisto", "titan", "enceladus", "rhea", "iapetus", "dione", "tethys",
    "mimas", "miranda", "ariel", "umbriel", "titania", "oberon", "triton",
    "nereid", "proteus", "charon", "nix", "hydra", "kerberos", "styx",
    "hyperion", "phoebe", "janus", "epimetheus", "helene", "telesto",
    "calypso", "atlas", "prometheus", "pandora", "pan", "daphnis", "puck",
    "portia", "rosalind", "cordelia", "ophelia", "desdemona", "juliet",
    "cressida", "belinda", "bianca", "sycorax", "prospero", "setebos",
    # Asteroids & minor planets
    "vesta", "pallas", "hygiea", "psyche", "eros", "ida", "gaspra",
    "itokawa", "bennu", "ryugu", "quaoar", "sedna", "varuna", "orcus",
    # Comets
    "halley", "encke", "borrelly", "swift_tuttle", "hale_bopp",
    # Galaxies
    "andromeda", "milkyway", "triangulum", "whirlpool", "sombrero",
    "cartwheel", "centaurus_a",
    # Nebulae
    "orion", "crab", "lagoon", "eagle", "helix", "bubble", "rosette",
    "pelican", "horsehead", "ring",
    # Constellations
    "aquarius", "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpius", "sagittarius", "capricornus", "pisces", "cygnus",
    "lyra", "draco", "cepheus", "cassiopeia", "perseus", "hercules",
    "ophiuchus", "monoceros", "centaurus", "auriga", "vulpecula",
    "delphinus", "lacerta", "lynx", "camelopardalis", "crater", "corvus",
    "columba", "grus", "dorado", "phoenix", "pavo", "musca", "tucana",
    "reticulum", "indus", "mensa", "volans", "chamaeleon", "octans",
    "apus",
]


# -------------------------------------------------------------------------------

def random_string(length: int) -> str:
    """Génère une chaîne alphanumérique aléatoire de longueur donnée."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_codename(
    prefix_length: int = 0,
    use_adjective: bool = True,
    use_adverb: bool = False,
    suffix_length: int = 0,
    separator: str = "-",
    style: Optional[str] = None
) -> str:
    # 🎨 Appliquer des presets par style
    if style == "ubuntu":
        use_adjective = True
        use_adverb = False
        prefix_length = 0
        suffix_length = 3
        separator = "-"
    elif style == "docker":
        use_adjective = False
        use_adverb = True
        prefix_length = 0
        suffix_length = 4
        separator = "-"
    elif style == "full":
        use_adjective = True
        use_adverb = True
        prefix_length = 3
        suffix_length = 4
        separator = "-"

    parts = []

    if prefix_length > 0:
        parts.append(random_string(prefix_length))

    if use_adverb:
        parts.append(random.choice(adverbs))

    if use_adjective:
        parts.append(random.choice(adjectives))

    # Toujours ajouter un nom d’objet céleste
    parts.append(random.choice(names))

    if suffix_length > 0:
        parts.append(random_string(suffix_length))

    return separator.join(parts)
