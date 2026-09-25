"""pairings.py — Cinema Food, Drink, Ambiance & Spotify Soundtrack Experience Engine.

Features:
- Iconic movie-specific gastronomic and cocktail Easter eggs.
- Genre-tailored culinary pairings with flavor profile descriptions.
- Mood-based sensory ambiance suggestions.
- Live Spotify embed playlist player matching mood and genre vibes.
"""

from typing import Any, Dict, List, Optional

# Curated Spotify soundtrack playlists tailored to mood & cinema vibe
SPOTIFY_MOOD_PLAYLISTS: Dict[str, Dict[str, str]] = {
    "joyful": {
        "title": "Feel-Good Cinematic Uplift",
        "uri": "playlist/37i9dQZF1DXdPec7aLTmlC",
        "embed_url": "https://open.spotify.com/embed/playlist/37i9dQZF1DXdPec7aLTmlC?utm_source=generator&theme=0",
        "vibe": "Upbeat pop anthems, sun-drenched melodies & bright horns",
    },
    "thrilling": {
        "title": "High-Tension Dark Noir & Bass",
        "uri": "playlist/37i9dQZF1DWWY64Hb7ZaNc",
        "embed_url": "https://open.spotify.com/embed/playlist/37i9dQZF1DWWY64Hb7ZaNc?utm_source=generator&theme=0",
        "vibe": "Pulsing sub-bass, industrial percussion & Hitchcockian strings",
    },
    "adventurous": {
        "title": "Epic Symphony & Cosmic Odyssey",
        "uri": "playlist/37i9dQZF1DX1tz6EDao8it",
        "embed_url": "https://open.spotify.com/embed/playlist/37i9dQZF1DX1tz6EDao8it?utm_source=generator&theme=0",
        "vibe": "Orchestral brass, sweeping orchestral crescendos & interstellar synths",
    },
    "cozy": {
        "title": "Warm Acoustic Hearth & Lo-Fi Lounge",
        "uri": "playlist/37i9dQZF1DXcBWIGoYBM5M",
        "embed_url": "https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M?utm_source=generator&theme=0",
        "vibe": "Intimate fingerpicked guitars, mellow piano & gentle vinyl crackle",
    },
    "melancholy": {
        "title": "Deep Slate Piano, Rain & Contemplation",
        "uri": "playlist/37i9dQZF1DX7qK8ma5wgG1",
        "embed_url": "https://open.spotify.com/embed/playlist/37i9dQZF1DX7qK8ma5wgG1?utm_source=generator&theme=0",
        "vibe": "Solfeggio cello, distant ambient reverbs & poetic neo-classical keys",
    },
}

# Iconic movie-specific pairing Easter eggs
ICONIC_PAIRINGS: Dict[str, Dict[str, str]] = {
    "inception": {
        "food": "Layered Mille-Feuille Pastry & Dream Truffles",
        "food_desc": "Complex, multi-layered puff pastry mirroring inception levels.",
        "drink": "Espresso Martini (with a Totem garnish)",
        "drink_desc": "Caffeine-infused clarity to navigate the subconscious.",
        "ambiance": "Low ambient brass chords, ticking watch sounds, minimal warm lighting.",
        "vibe_icon": "🌀",
        "spotify_playlist": "playlist/37i9dQZF1DX1tz6EDao8it",
    },
    "interstellar": {
        "food": "Cosmic Salt-Crusted Beef Ribs & Roasted Corn",
        "food_desc": "Nod to Cooper's farm with space-age crystalline finishing salt.",
        "drink": "Smoked Black Hole Bourbon with Star-Anise",
        "drink_desc": "Deep oak smokiness echoing the gravity of Gargantua.",
        "ambiance": "Pitch-black room, twinkling starry ceiling projection, ticking clock soundtrack.",
        "vibe_icon": "🚀",
        "spotify_playlist": "playlist/37i9dQZF1DX1tz6EDao8it",
    },
    "the dark knight": {
        "food": "Midnight Charcoal Sliders & Truffle Parmesan Fries",
        "food_desc": "Crispy Gotham-black activated charcoal brioche with aged cheddar.",
        "drink": "Dark Knight Manhattan with Blood Orange Bitters",
        "drink_desc": "A bold, brooding rye cocktail for protectors of the night.",
        "ambiance": "Deep shadows, rain-streaked window audio, neon city glow.",
        "vibe_icon": "🦇",
        "spotify_playlist": "playlist/37i9dQZF1DWWY64Hb7ZaNc",
    },
    "pulp fiction": {
        "food": "Big Kahuna Hawaiian Burger & Sweet Potato Wedges",
        "food_desc": "Charbroiled teriyaki beef with grilled pineapple and jack cheese.",
        "drink": "The $5 Gourmet Vanilla Shake (Spiked Bourbon optional)",
        "drink_desc": "Thick custard milkshake, decadent enough to make Vincent Vega approve.",
        "ambiance": "Retro diner vinyls, surf rock background, warm neon amber lights.",
        "vibe_icon": "🍔",
        "spotify_playlist": "playlist/37i9dQZF1DXdPec7aLTmlC",
    },
    "the godfather": {
        "food": "Sicilian Sunday Gravy Rigatoni & Pistachio Cannoli",
        "food_desc": "Slow-simmered garlic tomato ragu, finished with sweet ricotta pastry.",
        "drink": "Chianti Classico Riserva (Full-Bodied Tuscan Red)",
        "drink_desc": "Rich dark cherries and leather notes worthy of Don Corleone.",
        "ambiance": "Candlelit mahogany table, vintage Italian accordion melodies, velvet draping.",
        "vibe_icon": "🍷",
        "spotify_playlist": "playlist/37i9dQZF1DX7qK8ma5wgG1",
    },
    "toy story": {
        "food": "Pizza Planet Pepperoni Slice & Cheesy Stuffed Crust",
        "food_desc": "Retro arcade parlor pizza dripping with hot melted mozzarella.",
        "drink": "Alien Green Apple Sparkler (with Pop Rocks)",
        "drink_desc": "Zesty, electric green fizz with popping space-candy finish.",
        "ambiance": "Nostalgic 90s bedroom glow, starry desk lamp, cozy quilt blanket.",
        "vibe_icon": "🤠",
        "spotify_playlist": "playlist/37i9dQZF1DXdPec7aLTmlC",
    },
    "spirited away": {
        "food": "Steamed Anman Red Bean Buns & Giant Izakaya Baobao",
        "food_desc": "Cloud-soft steamed buns filled with sweet red bean paste and savory pork.",
        "drink": "Iced Jasmine Green Tea with Lychee Pearls",
        "drink_desc": "Fragrant floral green tea with sweet, chewy lychee boba.",
        "ambiance": "Glowing red paper lanterns, gentle summer rain audio, incense fragrance.",
        "vibe_icon": "🏮",
        "spotify_playlist": "playlist/37i9dQZF1DXcBWIGoYBM5M",
    },
}

GENRE_PAIRINGS: Dict[str, Dict[str, str]] = {
    "Action": {
        "food": "Korean Fried Chicken with Gochujang Glaze & Pickled Radish",
        "food_desc": "Ultra-crispy double-fried chicken with fiery, savory Korean crunch.",
        "drink": "Ice-Cold Craft IPA or Ginger Highball with Fresh Lime",
        "drink_desc": "Crisp, hoppy bitterness that slices through rich heat and grease.",
        "ambiance": "High volume, dim stadium spotlights, thrilling dynamic bass.",
        "vibe_icon": "💥",
    },
    "Adventure": {
        "food": "Wood-Fired Campfire Flatbread with Prosciutto & Wild Herbs",
        "food_desc": "Smoky charred dough baked over cedar wood, finished with mountain honey.",
        "drink": "Spiced Rum Swizzle or Mountain Huckleberry Lemonade",
        "drink_desc": "Tropical oak spice blended with tart wild forest berries.",
        "ambiance": "Golden campfire glow, gentle forest wind audio, natural woods.",
        "vibe_icon": "🧭",
    },
    "Animation": {
        "food": "Caramel Drizzle Rainbow Kettle Corn & M&M Pretzels",
        "food_desc": "Sweet-and-salty carnival popcorn with colorful chocolate pretzel bites.",
        "drink": "Bubble Tea with Brown Sugar Boba or Sparkling Berry Punch",
        "drink_desc": "Chewy caramelized tapioca pearls bathed in silky milk tea.",
        "ambiance": "Playful rainbow fairy lights, beanbags, cozy relaxed seating.",
        "vibe_icon": "🎨",
    },
    "Comedy": {
        "food": "Loaded Birria Tacos with Consomé Dip & Cilantro",
        "food_desc": "Crispy pan-fried corn tortillas packed with tender shredded beef and cheese.",
        "drink": "Spicy Mango Margarita with Tajín Rim or Craft Ginger Beer",
        "drink_desc": "Sweet tropical mango balanced with chili lime zest and tequila.",
        "ambiance": "Warm vibrant living room, friends on the sofa, casual laugh track ready.",
        "vibe_icon": "🌮",
    },
    "Crime": {
        "food": "Prosciutto, Fig, and Gorgonzola Flatbread",
        "food_desc": "Sophisticated Italian underworld elegance with a touch of sweetness.",
        "drink": "Classic Negroni (Campari, Sweet Vermouth, Gin)",
        "drink_desc": "Bitter, herbaceous, and timelessly stylish like a vintage mobster.",
        "ambiance": "Venetian blinds casting linear shadows, jazz saxophone, smoky aroma.",
        "vibe_icon": "🕵️",
    },
    "Documentary": {
        "food": "Artisan Mezze Platter (Hummus, Kalamata Olives, Warm Pita)",
        "food_desc": "Thoughtfully sourced Mediterranean bites inviting contemplative tasting.",
        "drink": "Matcha Green Tea or Single-Origin Ethiopian Pour-Over",
        "drink_desc": "Complex floral notes with gentle natural caffeine to keep intellect alert.",
        "ambiance": "Focused studio desk lamp, calm silence, notebook on hand.",
        "vibe_icon": "🎥",
    },
    "Drama": {
        "food": "Artisan Charcuterie Board with Aged Gouda & Marcona Almonds",
        "food_desc": "A thoughtful assortment of flavors that reward slow, measured tasting.",
        "drink": "Rich California Pinot Noir or Earl Grey Lavender Infusion",
        "drink_desc": "Complex notes of dark fruit, earth, and soothing florals.",
        "ambiance": "Subdued mood lighting, silence in the house, screen-focused focus.",
        "vibe_icon": "🎭",
    },
    "Fantasy": {
        "food": "Rosemary Garlic Focaccia with Wild Mushroom Pâté",
        "food_desc": "Earthbound tavern feast fit for elves, dwarves, and wanderers.",
        "drink": "Spiced Mulled Cider with Star Anise or Honey Mead",
        "drink_desc": "Aromatic brewing kettle warmth infused with honey and clove.",
        "ambiance": "Enchanted forest lantern glow, crackling hearth fire sounds.",
        "vibe_icon": "🧙",
    },
    "Horror": {
        "food": "Bloody Beetroot Bruschetta with Goat Cheese & Balsamic Reduction",
        "food_desc": "Crimson glazed beet cubes on garlic-rubbed grilled sourdough.",
        "drink": "Blood Orange Negroni or Tart Black Cherry Spritzer",
        "drink_desc": "Ominously dark red, dry, and startlingly bitter-sweet.",
        "ambiance": "Pitch darkness with single flickering candle, sudden sound ready.",
        "vibe_icon": "💀",
    },
    "Mystery": {
        "food": "Smoked Salmon Crostini with Dill Cream Cheese & Capers",
        "food_desc": "Sharp, intricate layers where every ingredient is a clue to savor.",
        "drink": "Foggy London Dry Gin & Tonic with Juniper Berries",
        "drink_desc": "Crisp botanicals shrouded in effervescent tonic mist.",
        "ambiance": "Looming shadows, rain against windowpane audio, study lamp glow.",
        "vibe_icon": "🔍",
    },
    "Romance": {
        "food": "Chocolate Dipped Strawberries & Warm French Brie Croissants",
        "food_desc": "Silky dark Valrhona chocolate over ripe strawberries with buttery pastry.",
        "drink": "Pink French Rosé Champagne or Sparkling Strawberry Mocktail",
        "drink_desc": "Fine delicate bubbles with hints of wild raspberries and fresh roses.",
        "ambiance": "Soft pink and golden fairy lights, scented jasmine candle, plush cushions.",
        "vibe_icon": "🌹",
    },
    "Sci-Fi": {
        "food": "Molecular Truffle Potato Foam with Crispy Lotus Chips",
        "food_desc": "Futuristic textures combining airy velvet potato and crisp root chips.",
        "drink": "Neon Blue Curaçao Electric Tonic or Yuzu Sparkling Soda",
        "drink_desc": "UV-reactive electric cyan glow with sharp Japanese citrus tang.",
        "ambiance": "Cool cyberpunk cyan and magenta LED backlighting, atmospheric ambient synth.",
        "vibe_icon": "🚀",
    },
    "Thriller": {
        "food": "Wasabi Crusted Ahi Tuna Bites with Soy-Mirin Glaze",
        "food_desc": "Sharp nose-tingling wasabi heat keeping your adrenaline spiked.",
        "drink": "Smoky Mezcal Paloma with Grapefruit Salt",
        "drink_desc": "Oaxacan woodsmoke paired with bitter grapefruit bite.",
        "ambiance": "Stark noir high-contrast shadows, cold crimson backlighting.",
        "vibe_icon": "⏳",
    },
    "Western": {
        "food": "Mesquite Smoked Pulled Pork Sliders with Pickled Jalapeños",
        "food_desc": "Slow-cooked Texas pork butt piled high on buttery brioche buns.",
        "drink": "Kentucky Rye Whiskey with Honey & Fresh Thyme",
        "drink_desc": "Spicy grain notes softened by wildflower honey and garden herbs.",
        "ambiance": "Warm rustic wood, sunset amber lantern glow, acoustic guitar.",
        "vibe_icon": "🤠",
    },
}

MOOD_PAIRINGS: Dict[str, Dict[str, str]] = {
    "joyful": {
        "food": "Crispy Churro Bites with Salted Caramel & Vanilla Ice Cream",
        "food_desc": "Golden fried cinnamon pastry dipped in rich velvety warm dulce de leche.",
        "drink": "Golden Passionfruit Spritz with Fresh Mint",
        "drink_desc": "Bright, effervescent tropical sparkle radiating golden energy.",
        "ambiance": "Warm golden amber lighting, joyful house vibes, aromatic sweet baking.",
        "vibe_icon": "☀️",
    },
    "thrilling": {
        "food": "Charred Habanero BBQ Chicken Wings with Cool Ranch",
        "food_desc": "Sticky, smoky heat that matches the escalating cinematic stakes.",
        "drink": "Crimson Blood Orange & Chili Mezcalita",
        "drink_desc": "Earthy smoke with sharp citrus acidity and tongue-tingling rim.",
        "ambiance": "Stark shadows, low crimson ambient glow, heart-rate audio.",
        "vibe_icon": "⚡",
    },
    "adventurous": {
        "food": "Baja Fish Tacos with Chipotle Slaw & Lime",
        "food_desc": "Beer-battered cod on warm corn tortillas with zesty cabbage crunch.",
        "drink": "Pineapple Coconut Caipirinha",
        "drink_desc": "Muddled fresh limes with Brazilian cachaça and toasted coconut.",
        "ambiance": "Emerald forest ambient glow, expedition gear aesthetic.",
        "vibe_icon": "🧭",
    },
    "cozy": {
        "food": "Four-Cheese Truffle Baked Macaroni & Garlic Herb Toast",
        "food_desc": "Gruyère, sharp cheddar, fontina, and parmigiano baked to bubbly perfection.",
        "drink": "Spiced Mexican Hot Chocolate with Marshmallow Cream",
        "drink_desc": "Dark cocoa spiked with cinnamon, chili, and vanilla whipped topping.",
        "ambiance": "Soft lavender ambient lighting, oversized wool throw, warm fireplace.",
        "vibe_icon": "☕",
    },
    "melancholy": {
        "food": "French Onion Soup Gratinée with Melted Gruyère Crouton",
        "food_desc": "Deeply caramelized sweet onions in rich beef broth beneath toasted bread.",
        "drink": "Smoked Earl Grey Toddy with Raw Wildflower Honey",
        "drink_desc": "Comforting bergamot steam with soothing medicinal warmth.",
        "ambiance": "Deep slate blue reflections, gentle rain audio, dim desk reading lamp.",
        "vibe_icon": "🌧️",
    },
}


def get_movie_pairings(movie: Dict[str, Any], mood: str = "joyful") -> Dict[str, Any]:
    """Return tailored food, drink, ambiance, and Spotify playlist for a movie.
    
    Checks in order:
    1. Iconic movie title specific Easter eggs.
    2. Dominant film genre profile.
    3. Active mood profile fallback.
    """
    clean_title = str(movie.get("title", "")).strip().lower()
    mood_key = mood.lower() if mood else "joyful"
    if mood_key not in SPOTIFY_MOOD_PLAYLISTS:
        mood_key = "joyful"

    spotify_info = SPOTIFY_MOOD_PLAYLISTS[mood_key]

    # 1. Iconic title matching
    for key, pairing in ICONIC_PAIRINGS.items():
        if key in clean_title:
            result = pairing.copy()
            result["spotify"] = spotify_info
            return result

    # 2. Genre matching
    genres = movie.get("genres", [])
    if isinstance(genres, str):
        genres = [g.strip() for g in genres.split("|") if g.strip()]

    for g in genres:
        if g in GENRE_PAIRINGS:
            result = GENRE_PAIRINGS[g].copy()
            if mood_key in MOOD_PAIRINGS:
                result["mood_hint"] = MOOD_PAIRINGS[mood_key]["ambiance"]
            result["spotify"] = spotify_info
            return result

    # 3. Mood fallback
    if mood_key in MOOD_PAIRINGS:
        result = MOOD_PAIRINGS[mood_key].copy()
        result["spotify"] = spotify_info
        return result

    # Default cinema general pairing
    return {
        "food": "Gourmet Truffle & Butter Cinema Popcorn",
        "food_desc": "Warm, freshly popped corn tossed in European butter and white truffle oil.",
        "drink": "Craft Dark Cherry Soda or Smoked Old Fashioned",
        "drink_desc": "Rich, fizzy, and perfectly balanced cinema beverage.",
        "ambiance": "Dim amber lighting, cozy velvet throws, cinematic sound.",
        "vibe_icon": "🍿",
        "spotify": spotify_info,
    }
