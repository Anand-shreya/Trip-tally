import asyncio

SRI_LANKA_PLACES = [
    {
        "name": "Kandy",
        "description": "Temple courtyards, lake walks, and the cultural heart of the hills.",
        "latitude": 7.2906,
        "longitude": 80.6337,
        "days": 2,
        "factor": 0.94,
        "best_for": ["Culture", "History"],
    },
    {
        "name": "Ella",
        "description": "Misty tea country, ridge hikes, and slow train journeys.",
        "latitude": 6.8667,
        "longitude": 81.0466,
        "days": 2,
        "factor": 0.88,
        "best_for": ["Nature", "Hiking"],
    },
    {
        "name": "Yala",
        "description": "Dawn safaris through scrubland known for leopards and elephants.",
        "latitude": 6.3725,
        "longitude": 81.5185,
        "days": 1,
        "factor": 1.18,
        "best_for": ["Wildlife", "Photography"],
    },
    {
        "name": "Mirissa",
        "description": "A relaxed southern coast base for coves and ocean mornings.",
        "latitude": 5.9483,
        "longitude": 80.4716,
        "days": 2,
        "factor": 1.05,
        "best_for": ["Beach", "Food"],
    },
    {
        "name": "Sigiriya",
        "description": "An ancient rock citadel rising above forest and water gardens.",
        "latitude": 7.9570,
        "longitude": 80.7603,
        "days": 1,
        "factor": 1.02,
        "best_for": ["History", "Views"],
    },
    {
        "name": "Galle",
        "description": "Fort ramparts, shaded lanes, and a layered maritime history.",
        "latitude": 6.0329,
        "longitude": 80.2168,
        "days": 1,
        "factor": 1.12,
        "best_for": ["Architecture", "Food"],
    },
]


async def get_candidate_places(destination: str) -> list[dict]:
    await asyncio.sleep(0)
    if "sri lanka" in destination.lower():
        return [dict(place) for place in SRI_LANKA_PLACES]
    base = destination.strip().title()
    themes = [
        ("Old Quarter", "Walkable heritage streets and local food", ["Culture", "Food"]),
        ("Nature Reserve", "A restorative day among native landscapes", ["Nature", "Wildlife"]),
        (
            "Market District",
            "Independent makers, regional produce, and evening energy",
            ["Shopping", "Food"],
        ),
        ("Riverside", "An easy waterfront route with relaxed stops", ["Views", "Leisure"]),
        ("Museum Quarter", "A focused introduction to local art and history", ["Art", "History"]),
    ]
    return [
        {
            "name": f"{base} {name}",
            "description": description,
            "latitude": 12.0 + index,
            "longitude": 77.0 + index,
            "days": 1 if index > 1 else 2,
            "factor": 0.9 + index * 0.08,
            "best_for": best_for,
        }
        for index, (name, description, best_for) in enumerate(themes)
    ]
