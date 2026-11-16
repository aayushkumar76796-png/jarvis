"""NCERT book / chapter lists (rationalised syllabus). If YOUR edition differs, pick
'Custom' in the app or edit the chapter list - lists are only a convenient starting point."""

CLASSES = ["6", "7", "8", "9", "10", "11", "12"]
LEVELS = ["Basic (NCERT only)", "Board - Medium", "Board - Hard / HOTS", "Olympiad / Advanced", "Last-minute revision"]

NCERT = {
    "10": {
        "Mathematics": {"book": "Mathematics (NCERT Class 10)", "chapters": [
            "Real Numbers", "Polynomials", "Pair of Linear Equations in Two Variables", "Quadratic Equations",
            "Arithmetic Progressions", "Triangles", "Coordinate Geometry", "Introduction to Trigonometry",
            "Some Applications of Trigonometry", "Circles", "Areas Related to Circles", "Surface Areas and Volumes",
            "Statistics", "Probability"]},
        "Science": {"book": "Science (NCERT Class 10)", "chapters": [
            "Chemical Reactions and Equations", "Acids, Bases and Salts", "Metals and Non-metals", "Carbon and its Compounds",
            "Life Processes", "Control and Coordination", "How do Organisms Reproduce?", "Heredity",
            "Light - Reflection and Refraction", "The Human Eye and the Colourful World", "Electricity",
            "Magnetic Effects of Electric Current", "Our Environment"]},
        "Social Science - History": {"book": "India and the Contemporary World - II", "chapters": [
            "The Rise of Nationalism in Europe", "Nationalism in India", "The Making of a Global World",
            "The Age of Industrialisation", "Print Culture and the Modern World"]},
        "Social Science - Geography": {"book": "Contemporary India - II", "chapters": [
            "Resources and Development", "Forest and Wildlife Resources", "Water Resources", "Agriculture",
            "Minerals and Energy Resources", "Manufacturing Industries", "Lifelines of National Economy"]},
        "Social Science - Political Science": {"book": "Democratic Politics - II", "chapters": [
            "Power Sharing", "Federalism", "Gender, Religion and Caste", "Political Parties", "Outcomes of Democracy"]},
        "Social Science - Economics": {"book": "Understanding Economic Development", "chapters": [
            "Development", "Sectors of the Indian Economy", "Money and Credit", "Globalisation and the Indian Economy",
            "Consumer Rights"]},
        "English - First Flight": {"book": "First Flight", "chapters": [
            "A Letter to God", "Nelson Mandela: Long Walk to Freedom", "Two Stories about Flying", "From the Diary of Anne Frank",
            "Glimpses of India", "Mijbil the Otter", "Madam Rides the Bus", "The Sermon at Benares", "The Proposal",
            "Poem: Dust of Snow", "Poem: Fire and Ice", "Poem: A Tiger in the Zoo", "Poem: How to Tell Wild Animals",
            "Poem: The Ball Poem", "Poem: Amanda!", "Poem: The Trees", "Poem: Fog", "Poem: The Tale of Custard the Dragon",
            "Poem: For Anne Gregory"]},
        "English - Footprints Without Feet": {"book": "Footprints Without Feet", "chapters": [
            "A Triumph of Surgery", "The Thief's Story", "The Midnight Visitor", "A Question of Trust",
            "Footprints without Feet", "The Making of a Scientist", "The Necklace", "Bholi", "The Book That Saved the Earth"]},
    },
    "9": {
        "Mathematics": {"book": "Mathematics (NCERT Class 9)", "chapters": [
            "Number Systems", "Polynomials", "Coordinate Geometry", "Linear Equations in Two Variables",
            "Introduction to Euclid's Geometry", "Lines and Angles", "Triangles", "Quadrilaterals", "Circles",
            "Heron's Formula", "Surface Areas and Volumes", "Statistics"]},
        "Science": {"book": "Science (NCERT Class 9)", "chapters": [
            "Matter in Our Surroundings", "Is Matter Around Us Pure?", "Atoms and Molecules", "Structure of the Atom",
            "The Fundamental Unit of Life", "Tissues", "Motion", "Force and Laws of Motion", "Gravitation",
            "Work and Energy", "Sound", "Improvement in Food Resources"]},
        "Social Science - History": {"book": "India and the Contemporary World - I", "chapters": [
            "The French Revolution", "Socialism in Europe and the Russian Revolution", "Nazism and the Rise of Hitler",
            "Forest Society and Colonialism", "Pastoralists in the Modern World"]},
        "Social Science - Geography": {"book": "Contemporary India - I", "chapters": [
            "India - Size and Location", "Physical Features of India", "Drainage", "Climate",
            "Natural Vegetation and Wildlife", "Population"]},
        "Social Science - Political Science": {"book": "Democratic Politics - I", "chapters": [
            "What is Democracy? Why Democracy?", "Constitutional Design", "Electoral Politics", "Working of Institutions",
            "Democratic Rights"]},
        "Social Science - Economics": {"book": "Economics (NCERT Class 9)", "chapters": [
            "The Story of Village Palampur", "People as Resource", "Poverty as a Challenge", "Food Security in India"]},
    },
}

# CBSE-style 80-mark written paper (3 hours)
PAPER_80 = [
    ("A", "Multiple-choice questions (incl. assertion-reason)", "20 x 1", 20),
    ("B", "Very short answer", "5 x 2", 10),
    ("C", "Short answer", "6 x 3", 18),
    ("D", "Long answer", "4 x 5", 20),
    ("E", "Case-based / source-based", "3 x 4", 12),
]
assert sum(p[3] for p in PAPER_80) == 80
