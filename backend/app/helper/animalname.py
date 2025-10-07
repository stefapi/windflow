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

adjectives = [
# Appearance adjectives (6)
    "bright", "clean", "clear", "glowing", "golden", "light",

# Emotion adjectives (11)
    "bold", "brave", "calm", "fun", "funky", "funny", "gentle", "happy", "kind", "smiling", "sweet",

# Intellect adjectives (8)
    "clever", "curious", "intense", "keen", "knowing", "logical", "smart", "wise",

# Size adjectives (4)
    "big", "huge", "massive", "mighty",

# Power adjectives (8)
    "fast", "heroic", "powerful", "quick", "sharp", "strong", "supreme", "vital",

# Morality adjectives (9)
    "adjusted", "fair", "honest", "just", "loyal", "noble", "pure", "sacred", "true",

# Mystical adjectives (5)
    "cosmic", "divine", "eternal", "free", "magical",

# Neutral_or_misc adjectives (398)
    "able", "above", "absolute", "accepted", "accurate", "ace", "active", "actual", "adapted",
    "adapting", "adequate", "advanced", "alert", "alive", "allowed", "allowing", "amazed",
    "amazing", "ample", "amused", "amusing", "apparent", "apt", "arriving", "artistic", "assured",
    "assuring", "awaited", "awake", "aware", "balanced", "becoming", "beloved", "better", "blessed",
    "boss", "brief", "bursting", "busy", "capable", "capital", "careful", "caring", "casual",
    "causal", "central", "certain", "champion", "charmed", "charming", "cheerful", "chief",
    "choice", "civil", "classic", "climbing", "close", "closing", "coherent", "comic", "communal",
    "complete", "composed", "concise", "concrete", "content", "cool", "correct", "crack", "creative",
    "credible", "crisp", "crucial", "cuddly", "cunning", "current", "cute", "daring", "darling",
    "dashing", "dear", "decent", "deciding", "deep", "definite", "delicate", "desired", "destined",
    "devoted", "direct", "discrete", "distinct", "diverse", "dominant", "driven", "driving",
    "dynamic", "eager", "easy", "electric", "elegant", "emerging", "eminent", "enabled", "enabling",
    "endless", "engaged", "engaging", "enhanced", "enjoyed", "enormous", "enough", "epic",
    "equal", "equipped", "ethical", "evident", "evolved", "evolving", "exact", "excited",
    "exciting", "exotic", "expert", "factual", "faithful", "famous", "fancy", "feasible", "fine",
    "finer", "firm", "first", "fit", "fitting", "fleet", "flexible", "flowing", "fluent", "flying",
    "fond", "frank", "fresh", "full", "game", "generous", "genuine", "giving", "glad", "glorious",
    "good", "gorgeous", "grand", "grateful", "great", "growing", "grown", "guided", "guiding",
    "handy", "hardy", "harmless", "healthy", "helped", "helpful", "helping", "hip", "holy",
    "hopeful", "hot", "humane", "humble", "humorous", "ideal", "immense", "immortal", "immune",
    "improved", "in", "included", "infinite", "informed", "innocent", "inspired", "integral",
    "intent", "internal", "intimate", "inviting", "joint", "key", "known", "large", "lasting",
    "leading", "learning", "legal", "legible", "lenient", "liberal", "liked", "literate", "live",
    "living", "loved", "loving", "lucky", "magnetic", "main", "major", "many", "master", "mature",
    "maximum", "measured", "meet", "merry", "mint", "model", "modern", "modest", "moral", "more",
    "moved", "moving", "musical", "mutual", "national", "native", "natural", "nearby", "neat",
    "needed", "neutral", "new", "next", "nice", "normal", "notable", "noted", "novel", "obliging",
    "on", "one", "open", "optimal", "optimum", "organic", "oriented", "outgoing", "patient",
    "peaceful", "perfect", "pet", "picked", "pleasant", "pleased", "pleasing", "poetic", "polished",
    "polite", "popular", "positive", "possible", "precious", "precise", "premium", "prepared",
    "present", "pretty", "primary", "prime", "pro", "probable", "profound", "promoted", "prompt",
    "proper", "proud", "proven", "pumped", "quality", "quiet", "rapid", "rare", "rational", "ready",
    "real", "refined", "regular", "related", "relative", "relaxed", "relaxing", "relevant",
    "relieved", "renewed", "renewing", "resolved", "rested", "rich", "right", "robust", "romantic",
    "ruling", "safe", "saved", "saving", "secure", "select", "selected", "sensible", "set",
    "settled", "settling", "sharing", "shining", "simple", "sincere", "singular", "skilled",
    "smashing", "smooth", "social", "solid", "sought", "sound", "special", "splendid", "square",
    "stable", "star", "steady", "sterling", "still", "stirred", "stirring", "striking", "stunning",
    "subtle", "suitable", "suited", "summary", "sunny", "super", "superb", "sure", "sweeping",
    "talented", "teaching", "tender", "thankful", "thorough", "tidy", "tight", "together",
    "tolerant", "top", "topical", "tops", "touched", "touching", "tough", "trusted", "trusting",
    "trusty", "ultimate", "unbiased", "uncommon", "unified", "unique", "united", "up", "upright",
    "upward", "usable", "useful", "valid", "valued", "vast", "verified", "viable", "vocal", "wanted",
    "warm", "wealthy", "welcome", "welcomed", "well", "whole", "willing", "winning", "wired",
    "witty", "wondrous", "workable", "working", "worthy",
]

adverbs = [
# Manner adverbs (316)
    "absently", "accurately", "actively", "actually", "amazingly", "apparently", "badly",
    "basically", "blinkedly", "blinkishly", "blinkly", "bobbleedly", "bobbleishly", "bobblely",
    "boldedly", "boldishly", "boldly", "breezeedly", "breezeishly", "breezely", "brightedly",
    "brightishly", "brightly", "briskedly", "briskishly", "briskly", "busily", "calmedly",
    "calmishly", "calmly", "clatteredly", "clatterly", "cleverly", "closely", "commonly",
    "completely", "confidently", "constantly", "correctly", "crispedly", "crispishly", "crisply",
    "curiously", "currently", "cuteedly", "cuteishly", "cutely", "dashedly", "dashishly", "dashly",
    "deadly", "directly", "distinctly", "eageredly", "eagerishly", "eagerly", "easily", "elegantly",
    "endlessly", "energetically", "entirely", "equally", "especially", "evenly", "evidently",
    "exactly", "explicitly", "extremely", "factually", "fairly", "famously", "fiercely", "firmly",
    "flareedly", "flareishly", "flarely", "flickedly", "flickishly", "flickly", "flipedly",
    "flipishly", "fliply", "floatedly", "floatishly", "floatly", "freeedly", "freeishly", "freely",
    "friendly", "fuzzedly", "fuzzishly", "fuzzly", "generally", "generously", "gentedly",
    "gentishly", "gentleedly", "gentleishly", "gentlely", "gently", "genuinely", "gladly",
    "gleamedly", "gleamishly", "gleamly", "glideedly", "glideishly", "glidely", "glintedly",
    "glintishly", "glintly", "globally", "glowedly", "glowishly", "glowly", "gradually", "greatly",
    "happily", "healthily", "heartily", "heavily", "highly", "hugely", "humbly", "hushedly",
    "hushishly", "hushly", "ideally", "immensely", "implicitly", "incredibly", "initially",
    "inquisitively", "intelligently", "intensely", "intentionally", "jolly", "kindly", "largely",
    "lazily", "lightly", "literally", "lively", "logically", "loudedly", "loudishly", "loudly",
    "lovely", "luckily", "mainly", "merrily", "moderately", "murmuredly", "murmurishly", "murmurly",
    "mutually", "mystedly", "mysteriously", "mystishly", "mystly", "naturally", "neatly", "nicely",
    "nudgeedly", "nudgeishly", "nudgely", "obediently", "openly", "passionately", "peepedly",
    "peepishly", "peeply", "perfectly", "personally", "plainly", "playfuledly", "pleasantly",
    "politely", "positively", "pranceedly", "pranceishly", "prancely", "precisely", "preferably",
    "presently", "previously", "primarily", "promptly", "properly", "proudly", "publicly",
    "puffedly", "puffishly", "puffly", "purely", "quickly", "quietly", "quirkedly", "quirkishly",
    "quirkly", "randomly", "rapidly", "readily", "reasonably", "regularly", "reliably", "remarkably",
    "repeatedly", "rightly", "rippleedly", "rippleishly", "ripplely", "roughly", "safely",
    "scurryedly", "scurryishly", "scurryly", "secretly", "seemingly", "sensibly", "separately",
    "seriously", "sharply", "shineedly", "shineishly", "shinely", "shortly", "silently", "simply",
    "sincerely", "skipedly", "skipishly", "skiply", "sleekedly", "sleekishly", "sleekly", "slightly",
    "slowly", "slyedly", "slyishly", "slyly", "smoothedly", "smoothishly", "smoothly", "sneakedly",
    "sneakishly", "sneakly", "sniffedly", "sniffishly", "sniffly", "snugedly", "snugishly", "snugly",
    "socially", "softedly", "softishly", "softly", "solely", "sparkedly", "sparkishly", "sparkly",
    "specially", "speedily", "sprintedly", "sprintishly", "sprintly", "steadily", "strangely",
    "strictly", "suddenly", "suitably", "swiftedly", "swiftishly", "swiftly", "thoroughly",
    "tightly", "twitchedly", "twitchishly", "twitchly", "typically", "ultimately", "uniformly",
    "uniquely", "urgently", "vaguely", "vastly", "verbally", "vigorously", "violently", "virtually",
    "visually", "warmedly", "warmishly", "warmly", "wearily", "whiffedly", "whiffishly", "whiffly",
    "whirledly", "whirlishly", "whirlly", "widely", "wiggleedly", "wiggleishly", "wigglely",
    "wildedly", "wildishly", "wildly", "willingly", "wisely", "zestedly", "zestishly", "zestly",
    "zingedly", "zingishly", "zingly",

# Frequency adverbs (2)
    "usually", "yearly",

# Degree adverbs (63)
    "blinkfully", "bobblefully", "boldfully", "breezefully", "brightfully", "briskfully",
    "calmfully", "crispfully", "cutefully", "dashfully", "eagerfully", "flarefully", "flickfully",
    "flipfully", "floatfully", "freefully", "fuzzfully", "gentfully", "gentlefully", "gleamfully",
    "glidefully", "glintfully", "glowfully", "hopefully", "hushfully", "loudfully", "mildly",
    "mostly", "murmurfully", "mystfully", "nudgefully", "peepfully", "playfully", "prancefully",
    "pufffully", "quirkfully", "ripplefully", "scurryfully", "shinefully", "skipfully", "sleekfully",
    "slyfully", "smoothfully", "sneakfully", "snifffully", "snugfully", "softfully", "sparkfully",
    "sprintfully", "strongly", "swiftfully", "thankfully", "totally", "twitchfully", "usefully",
    "utterly", "warmfully", "whifffully", "whirlfully", "wigglefully", "wildfully",
    "zestfully", "zingfully",

# Time adverbs (2)
    "instantly", "newly",

# Place adverbs (1)
    "locally",

# Affirmation adverbs (2)
    "really", "truly",

# Negation adverbs (0)

# Probability adverbs (1)
    "surely",

# Opinion adverbs (1)
    "honestly",
]


names = [
    # Large cats
    "panther", "wildcat", "tiger", "lion", "cheetah", "cougar", "leopard",
    "lioness", "liger", "bobcat", "ocelot", "lynx", "jaguar",

    # Snakes
    "viper", "cottonmouth", "python", "boa", "sidewinder", "cobra",
    "adder", "rattler", "moccasin", "asp", "anaconda",

    # Other predators
    "grizzly", "jackal", "falcon", "eagle", "hawk", "osprey", "goshawk",
    "wolf", "fox", "coyote", "hyena", "gator", "bear", "dog", "hound",
    "raptor", "weasel", "badger", "ferret", "mongoose", "beagle", "mastiff",
    "doberman", "akita", "husky", "malamute", "dingo", "jaguarundi",

    # Prey
    "wildebeest", "gazelle", "zebra", "elk", "moose", "deer", "stag", "pony",
    "koala", "sloth", "rabbit", "hare", "lamb", "fawn", "pika", "kid",
    "calf", "cow", "sheep", "doe", "pig", "pup", "piglet", "mule", "burro",
    "tapir", "guanaco", "yak", "oryx", "impala", "ibex", "reindeer",

    # Horses
    "horse", "stallion", "foal", "colt", "mare", "yearling", "filly", "gelding",
    "mustang",

    # Mythical creatures
    "mermaid", "unicorn", "fairy", "troll", "yeti", "pegasus", "griffin",
    "dragon", "phoenix", "ghost", "goblin", "ghoul", "werewolf", "basilisk",

    # Sea life
    "octopus", "lobster", "crab", "barnacle", "hammerhead", "orca", "piranha",
    "shark", "eel", "squid", "seal", "dolphin", "whale", "narwhal", "moray",
    "ray", "clam", "tuna", "cod", "bass", "trout", "salmon", "minnow",
    "mackerel", "marlin", "flounder", "perch", "bream", "polliwog", "catfish",
    "mudfish", "roughy", "sailfish", "pipefish", "shad", "tarpon", "snapper",
    "tetra", "halibut", "sculpin", "sturgeon", "anchovy", "bluegill", "bonefish",
    "oarfish", "dogfish", "monkfish", "sunfish", "goldfish", "mullet", "stingray",
    "urchin", "seahorse", "oyster", "snail", "crayfish", "slug",

    # Birds
    "owl", "raven", "crow", "jay", "robin", "sparrow", "finch", "crane", "heron",
    "egret", "swallow", "condor", "buzzard", "bluejay", "cardinal", "parrot",
    "pelican", "pheasant", "quail", "pigeon", "cockatoo", "starling", "macaw",
    "oriole", "grouse", "lark", "wren", "toucan", "sunbird", "thrush", "redbird",
    "stork", "kite", "swift", "mallard", "duck", "drake", "duckling", "goose",
    "gosling", "rook", "hummingbird",

    # Insects and bugs
    "bee", "wasp", "fly", "aphid", "mantis", "ladybug", "bedbug", "beetle",
    "earwig", "cricket", "moth", "flea", "tick", "gnat", "mosquito", "firefly",
    "dragonfly", "silkworm", "grub", "maggot", "lacewing", "katydid", "cicada",
    "weevil", "worm", "hookworm", "glowworm", "grubworm", "stinkbug", "midge",
    "sawfly", "spider", "scorpion", "locust",

    # Amphibians & reptiles
    "frog", "toad", "newt", "salamander", "lizard", "chameleon", "gecko",
    "skink", "iguana", "tortoise", "turtle", "terrapin",

    # Rodents & small mammals
    "rat", "mouse", "mole", "vole", "squirrel", "chipmunk", "muskrat", "lemming",
    "hamster", "gerbil", "gopher", "dormouse", "shrew",

    # Primates
    "chimp", "baboon", "monkey", "macaque", "gibbon", "gorilla", "orangutan",

    # Exotic mammals
    "kangaroo", "wombat", "hedgehog", "armadillo", "platypus", "opossum",
    "meerkat", "raccoon", "lemur", "marmot", "marten", "vervet", "wallaby",
    "quokka", "aardvark", "antelope", "bison", "buffalo", "caribou", "camel",
    "llama", "alpaca", "gnu", "okapi", "manatee", "orangutan", "dassie",
    "capybara", "pangolin", "mammoth", "mastodon",

    # Crustaceans & sea bugs
    "krill", "shrimp", "prawn", "barnacle", "anemone", "jellyfish", "seasnail",
    "scallop",

    # Other vertebrates
    "bat", "kit", "cub", "imp", "joey", "kid", "pup", "stud", "foal",
    "doe", "man", "calf", "buck", "bull", "boar", "hog",

    # Fantasy/alien/abstract
    "alien", "monster", "beast", "creature", "gargoyle", "entity", "banshee",
    "basilisk", "leviathan", "titan", "chimera", "nymph", "demon", "djinn",
    "wraith", "sprite", "shade"
]

def random_string(length: int) -> str:
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


    parts.append(random.choice(names))  # always include a name

    if suffix_length > 0:
        parts.append(random_string(suffix_length))

    return separator.join(parts)
