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

# 120 epic adjectives evoking mythic grandeur
adjectives = [
    "august", "auric", "abyssal", "arcane", "astral", "atavistic", "azure", "bardic", "beatific", "blessed",
    "brazen", "boundless", "cascade", "celestial", "chthonic", "colossal", "cosmic", "crimson", "cryptic", "cyclopean",
    "dauntless", "dawnlit", "destined", "divine", "dreaded", "druidic", "dusky", "eldritch", "emerald", "enchanted",
    "enduring", "eternal", "fabled", "fierce", "fiery", "forgotten", "fortified", "frosted", "galactic", "gilded",
    "glorious", "golden", "graceful", "hallowed", "heavenly", "heroic", "heroized", "immortal", "infinite", "invincible",
    "legendary", "luminous", "magical", "majestic", "mighty", "miraculous", "mystic", "myriad", "mythic", "noble",
    "numinous", "ominous", "omnipotent", "oracular", "otherworldly", "pagan", "phantom", "powerful", "primordial", "prophetic",
    "radiant", "runic", "sacred", "sagacious", "savage", "seraphic", "serene", "shadowy", "shamanic", "shining",
    "silver", "solar", "spectral", "spirited", "stellar", "stoic", "stormy", "stygian", "sublime", "supreme",
    "sunlit", "titanic", "tenacious", "terrible", "thunderous", "timeless", "transcendent", "undaunted", "unerring", "valiant",
    "venerable", "verdant", "vigilant", "vivid", "volatile", "warlike", "wayfaring", "whirling", "wild", "wise",
    "woven", "wyrd", "zenith", "chaotic", "dazzling", "glimmering", "harmonious", "lofty", "resplendent", "arcadian"
]

# 120 myth‑themed adverbs for extra flair
adverbs = [
    "augustly", "awesomely", "blessedly", "boldly", "celestially", "chaotically", "colossally", "cosmically", "cryptically", "dauntlessly",
    "divinely", "dreadfully", "eldritchly", "eternally", "fabulously", "fiercely", "fierily", "galactically", "glimmeringly", "gloriously",
    "godlike", "gracefully", "hallowedly", "heavenward", "heroically", "immortally", "infinitely", "invincibly", "legendarily", "luminously",
    "majestically", "mightily", "miraculously", "mystically", "mythically", "nobly", "numinously", "ominously", "oracularly", "otherworldly",
    "paganly", "phantasmally", "powerfully", "primordially", "prophetically", "radiantly", "runically", "sacredly", "sagely", "savagely",
    "serenely", "shadowily", "shamanically", "shiningly", "silvery", "solarward", "spectrally", "spiritually", "stellarly", "stoically",
    "stormily", "stygianly", "sublimely", "supremely", "titanically", "thunderously", "timelessly", "transcendently", "undauntedly", "unerringly",
    "valiantly", "venerably", "vigilantly", "vividly", "volatilely", "warlikely", "whirlingly", "wildly", "wisely", "wyrdly",
    "zealously", "zenithward", "arcanely", "atavically", "bardically", "beatifically", "brazenly", "boundlessly", "crimsonly", "cyclopeanly",
    "dawningly", "destinedly", "dragonishly", "druidically", "duskingly", "emeraldly", "enchantingly", "enduringly", "elysianly", "everlastingly",
    "frostily", "gildedly", "harmoniously", "immensely", "iridescently", "lorewise", "lyrically", "nocturnally", "obscurely", "phantasmically",
    "quixotically", "resplendently", "runewise", "shadowlessly", "sidereally", "spirally", "stormward", "sunward", "tempestuously", "terrestrially"
]

# 300 mythological figures grouped by pantheon & role

names = [
    # ============================= EGYPTIAN GODS ============================
    "Ra", "Osiris", "Isis", "Horus", "Set", "Anubis", "Thoth", "Bastet", "Sekhmet", "Hathor",
    "Nephthys", "Amun", "Ptah", "Sobek", "Khonsu", "Ma'at", "Nut", "Geb", "Shu", "Tefnut",
    "Serqet", "Wadjet", "Khepri", "Heka", "Hapi", "Atum", "Seshat", "Montu", "Khnum", "Apep",
    "Aten", "Menhit", "Pakhet", "Wepwawet", "Mehit", "Meretseger", "Renenutet", "Tayet", "Anuket", "Sobdet",
    "Wosret", "Ihy", "Qebehsenuef", "Duamutef", "Imsety", "Sopdu", "Heryshaf", "Ha", "Kek", "Kauket",

    # ========================== MESOPOTAMIAN GODS ==========================
    "Anu", "Enlil", "Enki", "Inanna", "Ishtar", "Marduk", "Tiamat", "Nergal", "Ereshkigal", "Shamash",
    "Sin", "Ashur", "Ninurta", "Lugalbanda", "Gilgamesh", "Humbaba", "Utnapishtim", "Dumuzi", "Adad", "Gugalanna",
    "Gibil", "Geshtinanna", "Lahmu", "Lahamu", "Nisaba", "Ashnan", "Nanshe", "Tashmetu", "Kingu", "BullOfHeaven",
    "Adapa", "Anshar", "Kishar", "Kakka", "Shulpae",

    # ============================= GREEK GODS ==============================
    "Zeus", "Hera", "Poseidon", "Demeter", "Athena", "Apollo", "Artemis", "Ares", "Hermes", "Hephaestus",
    "Aphrodite", "Hestia", "Dionysus", "Persephone", "Hades", "Cronus", "Rhea", "Gaia", "Uranus", "Helios",
    "Selene", "Nemesis", "Nike", "Eris", "Thanatos", "Eros", "Morpheus", "Nyx", "Atlas", "Hyperion",
    "Iapetus", "Coeus", "Crius", "Phoebe", "Theia", "Mnemosyne", "Themis", "Metis", "Leto", "Dione",
    "Hecate", "Harmonia", "Hebe", "Pan", "Eos", "Iris", "Astraeus", "Boreas", "Eurus", "Notus", "Zephyrus",

    # ============== GREEK HEROES & DEMI‑GODS (MORTAL OR BOTH) ==============
    "Heracles", "Perseus", "Theseus", "Jason", "Achilles", "Telemaque", "Orpheus", "Bellerophon", "Cadmus", "Oedipus",
    "Iphigenia", "Cassandra", "Andromeda", "Atalanta", "Achates", "Ganymede", "Triton", "Proteus", "Nereus", "Typhon",

    # =========== GREEK NYMPHS, MUSES & OTHER MINOR DIVINITIES =============
    "Galatea", "Aura", "Eileithyia", "Clio", "Euterpe", "Thalia", "Melpomene", "Terpsichore", "Erato", "Polyhymnia", "Urania",

    # ============================== ROMAN GODS =============================
    "Jupiter", "Juno", "Neptune", "Ceres", "Minerva", "Mars", "Mercury", "Vulcan", "Venus", "Vesta",
    "Bacchus", "Pluto", "Proserpina", "Janus", "Diana", "Aurora", "Cupid", "Fortuna", "Luna", "Sol",
    "Saturn", "Ops", "Faunus", "Flora", "Bellona", "Quirinus", "Portunus", "Terminus", "Silvanus", "Fauna",
    "Tellus", "Dis", "Vulturnus", "Volturnus", "Juturna", "Cardea", "Clementia", "Concordia", "Pietas", "Victoria",
    "Aeternitas", "Libertas", "Spes",

    # =========================== NORSE ÆSIR & VANIR =========================
    "Odin", "Frigg", "Thor", "Loki", "Balder", "Tyr", "Heimdall", "Freya", "Freyr", "Njord",
    "Skadi", "Idun", "Bragi", "Sif", "Vidar", "Vali", "Ullr", "Hel", "Fenrir", "Jormungandr",
    "Surt", "Ymir", "Mimir", "Kvasir", "Forseti", "Aegir", "Ran", "Kari", "Sigyn", "Hodr",

    # ===================== NORSE HEROES & LEGENDARY CREATURES ==============
    "Gullveig", "Hrungnir", "Garmr", "Hati", "Skoll", "Sleipnir",

    # ============================= CELTIC GODS ============================
    "Dagda", "Lugh", "Brigid", "Morrigan", "Cernunnos", "Arawn", "Rhiannon", "Nuada", "Epona", "Ogma",
    "Manannan", "Belenus", "Taranis", "Danu", "Angus", "Aine", "Donn", "Boann", "Cathubodua", "Creidhne",
    "Goibniu", "Lir", "Macha", "Neit", "Nemain", "Scathach", "Fand",

    # ======================== CELTIC HEROES & FIGURES ======================
    "Cuchulainn", "Balor", "Medb", "Aoife", "Grainne",

    # ============================== SLAVIC GODS ============================
    "Perun", "Veles", "Svarog", "Lada", "Morana", "Jarilo", "Chernobog", "Zorya", "Dazhbog", "Triglav",
    "Rod", "Stribog", "Belobog", "Zmey",

    # ========================== FINNO‑BALTIC GODS ==========================
    "Ukko", "Ilmatar", "Tapio", "Ahti", "Louhi", "Dievas", "Perkunas", "Vainamoinen", "Ilmarinen", "Kaleva",
    "Lemminkainen", "Kuu", "Mielikki", "Hiisi", "Kauko"
]

def random_string(length: int) -> str:
    """Return a random lowercase alphanumeric string of the given length."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_codename(
    prefix_length: int = 0,
    use_adjective: bool = True,
    use_adverb: bool = False,
    suffix_length: int = 0,
    separator: str = "-",
    style: Optional[str] = None,
) -> str:
    """Generate a memorable codename composed of random parts.

    Styles mimic popular schemes:
    - "ubuntu": adjective + myth name + 3‑char suffix
    - "docker": adverb + myth name + 4‑char suffix
    - "full": 3‑char prefix + adverb + adjective + myth name + 4‑char suffix
    """

    # Apply presets based on style
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

    # Always include a mythological name
    parts.append(random.choice(names))

    if suffix_length > 0:
        parts.append(random_string(suffix_length))

    return separator.join(parts)
