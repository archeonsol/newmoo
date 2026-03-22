"""
Full drug definitions: recipes, stages, effects, comedown, addiction, overdose.
"""

DRUGS = {
    "lethe": {
        "key": "lethe",
        "name": "Lethe",
        "desc": "A bright pink capsule. Blocks pain and wraps the user in heavy euphoria. Named for the river of forgetting.",
        "form": "capsule",
        "color": "bright pink",
        "recipe": {
            "chemicals": {"anima": 0.3, "tallow": 0.2, "prima_materia": 0.2},
            "base_yield": 4,
            "brew_station": "apothecary",
        },
        "stages": [
            {"name": "Dissolution", "duration_seconds": 180, "tend_action": "stir", "tend_desc": "You dissolve the anima into the tallow. The mixture clouds, then clears to a faint pink.", "skill_check_difficulty": 10, "quality_impact_success": 0, "quality_impact_fail": -12, "quality_impact_crit": 5},
            {"name": "Binding", "duration_seconds": 300, "tend_action": "heat", "tend_desc": "You apply low heat. The compounds bind. The pink deepens.", "skill_check_difficulty": 14, "quality_impact_success": 0, "quality_impact_fail": -18, "quality_impact_crit": 8},
            {"name": "Encapsulation", "duration_seconds": 120, "tend_action": "decant", "tend_desc": "You draw the liquid into capsule moulds. Each one sets with a faint click.", "skill_check_difficulty": 8, "quality_impact_success": 0, "quality_impact_fail": -10, "quality_impact_crit": 3},
        ],
        "effects": {
            "duration_seconds": 600,
            "stat_buffs": {"endurance": 15},
            "stat_debuffs": {"agility": -12},
            "special": ["pain_suppression"],
            "echo_onset": [
                "A warmth spreads from your stomach outward. The edges of everything go soft.",
                "The pain — all of it — recedes. Like a tide going out. You feel like cotton.",
                "Your limbs are heavy and light at the same time. Nothing hurts. Nothing matters.",
            ],
            "echo_active": [
                "The world is a comfortable blur. You feel good. You feel nothing.",
                "Sounds come from far away. Gravity is optional.",
            ],
        },
        "comedown": {
            "duration_seconds": 480,
            "stat_debuffs": {"perception": -8, "agility": -5},
            "echo_comedown": [
                "The warmth fades. The world sharpens — too sharp. Your head swims.",
                "Vertigo. The floor tilts. Your balance is wrong.",
                "A dull ache returns. Not where you were hurt. Everywhere.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.15,
            "tolerance_rate": 0.10,
            "withdrawal_debuffs": {"endurance": -10, "perception": -5},
            "withdrawal_echoes": [
                "Your skin itches from the inside. The old ache is back, and it brought friends.",
                "Everything hurts. Not injury-pain. Absence-pain. Your body wants what it had.",
            ],
        },
        "overdose_threshold": 2,
        "drug_category": "analgesic",
    },
    "quietus": {
        "key": "quietus",
        "name": "Quietus",
        "desc": "A small green hexagonal tablet marked with a Q. Kills all pain. Kills some other things too.",
        "form": "tablet",
        "color": "green",
        "recipe": {
            "chemicals": {"anima": 0.4, "vitriol_salt": 0.2, "iron_salt": 0.1},
            "base_yield": 3,
            "brew_station": "apothecary",
        },
        "stages": [
            {"name": "Extraction", "duration_seconds": 240, "tend_action": "filter", "tend_desc": "You filter the anima through vitriol-treated mesh. The runoff is green and still.", "skill_check_difficulty": 14, "quality_impact_success": 0, "quality_impact_fail": -15, "quality_impact_crit": 5},
            {"name": "Crystallization", "duration_seconds": 360, "tend_action": "cool", "tend_desc": "You cool the solution slowly. Hexagonal crystals form along the glass.", "skill_check_difficulty": 16, "quality_impact_success": 0, "quality_impact_fail": -20, "quality_impact_crit": 8},
            {"name": "Pressing", "duration_seconds": 180, "tend_action": "press", "tend_desc": "You press the crystals into tablets. Each one snaps from the mould with a clean edge.", "skill_check_difficulty": 10, "quality_impact_success": 0, "quality_impact_fail": -8, "quality_impact_crit": 3},
        ],
        "effects": {
            "duration_seconds": 720,
            "stat_buffs": {"endurance": 20},
            "stat_debuffs": {"agility": -15},
            "special": ["pain_suppression", "chrome_psychosis_reduction"],
            "echo_onset": [
                "The tablet dissolves on your tongue. Bitter. Then nothing. The pain stops. All of it.",
                "Your body goes quiet. Not numb — quiet. Like the nerves forgot how to complain.",
            ],
            "echo_active": [
                "You can't feel your extremities. This should worry you. It doesn't.",
            ],
        },
        "comedown": {
            "duration_seconds": 600,
            "stat_debuffs": {"endurance": -8, "agility": -8},
            "echo_comedown": [
                "Phantom pain. Your body remembers injuries that are already healed and reports them fresh.",
                "Your skin crawls. Itching that starts deep, beneath the muscle. You can't scratch it.",
                "Nausea. Your stomach rebels against the emptiness where the drug was.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.25,
            "tolerance_rate": 0.12,
            "withdrawal_debuffs": {"endurance": -15, "agility": -8, "perception": -5},
            "withdrawal_echoes": [
                "The pain is back. All of it. Every wound you've ever taken, remembered at once.",
                "Your hands shake. Not from cold. From need. The body knows what it wants.",
            ],
        },
        "overdose_threshold": 2,
        "drug_category": "opioid",
    },
    "prism": {
        "key": "prism",
        "name": "Prism",
        "desc": "A pre-filled syringe of iridescent liquid. The world becomes more than it is.",
        "form": "injectable",
        "color": "iridescent",
        "recipe": {
            "chemicals": {"mycelium_essence": 0.4, "phosphor": 0.2, "prima_materia": 0.2},
            "base_yield": 3,
            "brew_station": "synthesis",
        },
        "stages": [
            {"name": "Infusion", "duration_seconds": 300, "tend_action": "stir", "tend_desc": "The mycelium essence swirls into the phosphor. The color shifts — blue, green, violet. It won't settle.", "skill_check_difficulty": 12, "quality_impact_success": 0, "quality_impact_fail": -15, "quality_impact_crit": 8},
            {"name": "Stabilization", "duration_seconds": 480, "tend_action": "observe", "tend_desc": "You watch the mixture. It pulses. You adjust the temperature by fractions until the oscillation steadies.", "skill_check_difficulty": 18, "quality_impact_success": 0, "quality_impact_fail": -22, "quality_impact_crit": 10},
            {"name": "Draw", "duration_seconds": 120, "tend_action": "decant", "tend_desc": "You draw the solution into syringes. The liquid catches the light differently each time.", "skill_check_difficulty": 8, "quality_impact_success": 0, "quality_impact_fail": -8, "quality_impact_crit": 3},
        ],
        "effects": {
            "duration_seconds": 900,
            "stat_buffs": {"perception": 18},
            "stat_debuffs": {"agility": -10, "intelligence": -8},
            "special": ["visual_color_shift", "hallucination_mild"],
            "echo_onset": [
                "The needle goes in. The world |cbrightens|n. Colors you've never seen bloom at the edges of everything.",
                "The walls are breathing. The light has a sound. Your skin tastes the air.",
                "You can see the |mfrequencies|n. Every surface is alive with patterns that were always there.",
            ],
            "echo_active": [
                "Colors |cpulse|n in time with your heartbeat. The world is |mbeautiful|n and |runtrustworthy|n.",
                "Someone's voice has a |ccolor|n. You can't remember which word means which sense.",
            ],
        },
        "comedown": {
            "duration_seconds": 540,
            "stat_debuffs": {"perception": -6, "agility": -4},
            "echo_comedown": [
                "The colors fade. The world is grey again. It was always grey. You just forgot.",
                "Your reaction time is shot. Hot and cold flashes. The grey feels personal.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.12,
            "tolerance_rate": 0.15,
            "withdrawal_debuffs": {"perception": -10},
            "withdrawal_echoes": [
                "Everything is flat. The world lacks dimension. You remember when it was more.",
            ],
        },
        "overdose_threshold": 2,
        "drug_category": "psychedelic",
    },
    "third_eye": {
        "key": "third_eye",
        "name": "Third Eye",
        "desc": "Tiny blue pyramids on wax paper. Mild, steady, and deceptively gentle.",
        "form": "sublingual",
        "color": "pale blue",
        "recipe": {
            "chemicals": {"mycelium_essence": 0.2, "prima_materia": 0.3, "ferment": 0.1},
            "base_yield": 6,
            "brew_station": "apothecary",
        },
        "stages": [
            {"name": "Culturing", "duration_seconds": 600, "tend_action": "observe", "tend_desc": "The broth cultures in the solution. You watch for the right shade of blue.", "skill_check_difficulty": 10, "quality_impact_success": 0, "quality_impact_fail": -10, "quality_impact_crit": 5},
            {"name": "Drying", "duration_seconds": 300, "tend_action": "heat", "tend_desc": "Low heat. The liquid evaporates. Blue crystals form in pyramid shapes on the wax paper.", "skill_check_difficulty": 12, "quality_impact_success": 0, "quality_impact_fail": -12, "quality_impact_crit": 5},
        ],
        "effects": {
            "duration_seconds": 1200,
            "stat_buffs": {"perception": 10},
            "stat_debuffs": {"agility": -5},
            "special": ["hallucination_mild"],
            "echo_onset": [
                "It dissolves under your tongue. A gentle warmth. The world sharpens at the edges.",
                "Mild. Pleasant. The light has more detail than before. You notice things you missed.",
            ],
            "echo_active": [
                "A subtle shimmer at the periphery. Not hallucination — more like noticing what was already there.",
            ],
        },
        "comedown": {
            "duration_seconds": 300,
            "stat_debuffs": {"agility": -3},
            "echo_comedown": [
                "A brief chill. The sharpness fades. Back to baseline. Barely noticeable.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.08,
            "tolerance_rate": 0.08,
            "withdrawal_debuffs": {"perception": -5},
            "withdrawal_echoes": [
                "The world feels slightly out of focus. Like you need glasses you never owned.",
            ],
        },
        "overdose_threshold": 3,
        "drug_category": "psychedelic",
    },
    "mercurial": {
        "key": "mercurial",
        "name": "Mercurial",
        "desc": "A fine white powder in a clear capsule. Everything accelerates. Including the parts of you that shouldn't.",
        "form": "capsule",
        "color": "white",
        "recipe": {
            "chemicals": {"ichor": 0.2, "galvanic_salt": 0.2, "aqua_fortis": 0.2, "prima_materia": 0.1},
            "base_yield": 4,
            "brew_station": "synthesis",
        },
        "stages": [
            {"name": "Synthesis", "duration_seconds": 360, "tend_action": "heat", "tend_desc": "You heat the ichor in solvent. The reaction is exothermic — the glass is hot to touch.", "skill_check_difficulty": 16, "quality_impact_success": 0, "quality_impact_fail": -18, "quality_impact_crit": 8},
            {"name": "Electrolysis", "duration_seconds": 240, "tend_action": "observe", "tend_desc": "You run current through the solution. The electrolyte compound catalyzes. Bubbles rise.", "skill_check_difficulty": 14, "quality_impact_success": 0, "quality_impact_fail": -15, "quality_impact_crit": 5},
            {"name": "Crystallization", "duration_seconds": 300, "tend_action": "cool", "tend_desc": "Cooling. The powder precipitates — white, fine, potent. You scrape it into capsules.", "skill_check_difficulty": 12, "quality_impact_success": 0, "quality_impact_fail": -10, "quality_impact_crit": 5},
        ],
        "effects": {
            "duration_seconds": 480,
            "stat_buffs": {"intelligence": 15, "charisma": 10},
            "stat_debuffs": {"agility": -8},
            "special": [],
            "echo_onset": [
                "The capsule hits your system. Your heart rate doubles. Your thoughts race — clear, sharp, connected.",
                "Everything slows down. Not you. The world. You are moving at the right speed. They are all behind.",
            ],
            "echo_active": [
                "Your mind is a machine. Every thought follows the last without gap. You are brilliant.",
                "Your hands are shaking. Your brain doesn't care. It has better things to think about.",
            ],
        },
        "comedown": {
            "duration_seconds": 600,
            "stat_debuffs": {"intelligence": -10, "charisma": -8, "endurance": -5},
            "echo_comedown": [
                "The crash. Your blood pressure spikes — you can feel your pulse in your eyes.",
                "Nosebleed. The blood is bright and sudden. Your thoughts are thick, sluggish, ordinary.",
                "Synaptic burnout. The world is slow and you are slow with it.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.20,
            "tolerance_rate": 0.12,
            "withdrawal_debuffs": {"intelligence": -12, "charisma": -8},
            "withdrawal_echoes": [
                "Fog. Your thoughts won't connect. You had something important to think about. It's gone.",
            ],
        },
        "overdose_threshold": 2,
        "drug_category": "stimulant",
    },
    "vitriol": {
        "key": "vitriol",
        "name": "Vitriol",
        "desc": "A syringe of amber liquid. Raw power in a needle. The Burn quarter's signature product.",
        "form": "injectable",
        "color": "amber",
        "recipe": {
            "chemicals": {"ichor": 0.3, "iron_salt": 0.2, "tallow": 0.2},
            "base_yield": 3,
            "brew_station": "synthesis",
        },
        "stages": [
            {"name": "Binding", "duration_seconds": 240, "tend_action": "stir", "tend_desc": "The ichor binds to the iron salt. The liquid turns amber — the color of heated metal.", "skill_check_difficulty": 14, "quality_impact_success": 0, "quality_impact_fail": -15, "quality_impact_crit": 5},
            {"name": "Fortification", "duration_seconds": 360, "tend_action": "heat", "tend_desc": "You heat it until the tallow suspends the compound. It smells like hot copper.", "skill_check_difficulty": 18, "quality_impact_success": 0, "quality_impact_fail": -20, "quality_impact_crit": 8},
            {"name": "Draw", "duration_seconds": 120, "tend_action": "decant", "tend_desc": "Into syringes. The amber liquid is thick. It will feel like fire going in.", "skill_check_difficulty": 10, "quality_impact_success": 0, "quality_impact_fail": -8, "quality_impact_crit": 3},
        ],
        "effects": {
            "duration_seconds": 540,
            "stat_buffs": {"strength": 18, "endurance": 12},
            "stat_debuffs": {"intelligence": -12},
            "special": [],
            "echo_onset": [
                "The needle burns going in. Then YOU burn. Heat in your veins, in your muscles, in your jaw.",
                "You are stronger. You know this the way you know gravity. Your fists feel like hammers.",
            ],
            "echo_active": [
                "Your muscles hum. Everything you lift is lighter. Everything you hit breaks easier.",
                "Thinking is hard. Thinking is unnecessary. Your body knows what to do.",
            ],
        },
        "comedown": {
            "duration_seconds": 480,
            "stat_debuffs": {"strength": -10, "endurance": -8, "agility": -5},
            "echo_comedown": [
                "The strength drains out of you like heat from cooling metal. Your muscles ache.",
                "Tremors. Your hands won't stop shaking. Your jaw is clenched and won't unlock.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.18,
            "tolerance_rate": 0.10,
            "withdrawal_debuffs": {"strength": -12, "endurance": -8},
            "withdrawal_echoes": [
                "Weakness. Real weakness. The kind where your arms are too heavy to lift.",
            ],
        },
        "overdose_threshold": 2,
        "drug_category": "stimulant",
    },
    "greenmote": {
        "key": "greenmote",
        "name": "Greenmote",
        "desc": "A pre-rolled joint of modified fungal fiber. The Sink's cash crop. Smells earthy, hits gentle.",
        "form": "smoked",
        "color": "grey-green",
        "recipe": {
            "chemicals": {"mycelium_essence": 0.1, "ferment": 0.2, "tallow": 0.1},
            "base_yield": 8,
            "brew_station": "apothecary",
        },
        "stages": [
            {"name": "Culturing", "duration_seconds": 480, "tend_action": "observe", "tend_desc": "The fungal culture grows on the fiber. You watch for the right density of mycelia.", "skill_check_difficulty": 8, "quality_impact_success": 0, "quality_impact_fail": -10, "quality_impact_crit": 5},
            {"name": "Drying", "duration_seconds": 600, "tend_action": "heat", "tend_desc": "Low heat drying. Too hot and you destroy the active compound. Too cold and it moulds.", "skill_check_difficulty": 10, "quality_impact_success": 0, "quality_impact_fail": -12, "quality_impact_crit": 5},
            {"name": "Rolling", "duration_seconds": 60, "tend_action": "press", "tend_desc": "You roll the dried fiber into joints. Simple. Honest. The Sink's oldest skill.", "skill_check_difficulty": 5, "quality_impact_success": 0, "quality_impact_fail": -5, "quality_impact_crit": 2},
        ],
        "effects": {
            "duration_seconds": 900,
            "stat_buffs": {"intelligence": 8},
            "stat_debuffs": {"agility": -6},
            "special": ["hunger_increase", "tolerance_buildup_fast"],
            "echo_onset": [
                "You light it. The smoke is thick, earthy, with a faint sweetness. Your first exhale is slow.",
                "The tension goes out of your shoulders. Your thoughts wander, but gently.",
            ],
            "echo_active": [
                "Everything is a little funnier than it should be. Your thoughts meander.",
                "You're hungry. Very hungry. When did you last eat?",
            ],
        },
        "comedown": {
            "duration_seconds": 300,
            "stat_debuffs": {"agility": -3},
            "echo_comedown": [
                "Sluggish. Sleepy. The mellow fades into lethargy.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.20,
            "tolerance_rate": 0.20,
            "withdrawal_debuffs": {"intelligence": -5},
            "withdrawal_echoes": [
                "Irritable. Everything is slightly too loud, too bright, too much. You want another hit.",
            ],
        },
        "overdose_threshold": 4,
        "drug_category": "depressant",
    },
    "aqua_regia": {
        "key": "aqua_regia",
        "name": "Aqua Regia",
        "desc": "A vial of clear liquid with a reddish tint. Two minutes of invincibility. Then the bill comes due.",
        "form": "liquid",
        "color": "clear-red",
        "recipe": {
            "chemicals": {"ichor": 0.4, "sanguine": 0.3, "galvanic_salt": 0.2},
            "base_yield": 2,
            "brew_station": "synthesis",
        },
        "stages": [
            {"name": "Extraction", "duration_seconds": 300, "tend_action": "filter", "tend_desc": "You concentrate the ichor. The sanguine gives it oxygen-carrying capacity. The mix turns red.", "skill_check_difficulty": 20, "quality_impact_success": 0, "quality_impact_fail": -25, "quality_impact_crit": 10},
            {"name": "Catalysis", "duration_seconds": 420, "tend_action": "heat", "tend_desc": "The galvanic salt catalyzes the reaction. The vial is warm. The liquid shimmers.", "skill_check_difficulty": 22, "quality_impact_success": 0, "quality_impact_fail": -25, "quality_impact_crit": 10},
            {"name": "Stabilization", "duration_seconds": 360, "tend_action": "cool", "tend_desc": "You cool it slowly. Too fast and it denatures. The red deepens. It's ready.", "skill_check_difficulty": 18, "quality_impact_success": 0, "quality_impact_fail": -20, "quality_impact_crit": 8},
            {"name": "Bottling", "duration_seconds": 60, "tend_action": "decant", "tend_desc": "Into vials. Two doses. Handle with care.", "skill_check_difficulty": 10, "quality_impact_success": 0, "quality_impact_fail": -8, "quality_impact_crit": 3},
        ],
        "effects": {
            "duration_seconds": 180,
            "stat_buffs": {"agility": 20, "endurance": 20},
            "stat_debuffs": {"intelligence": -15},
            "special": ["pain_suppression", "bleeding_resistance"],
            "echo_onset": [
                "|RYOUR HEART RATE TRIPLES.|n Everything is too bright, too loud, too fast. You are |rready|n.",
                "Your muscles are on fire. Your hands are steady. Fear is a concept. Not yours.",
            ],
            "echo_active": [
                "You are a weapon. The chemistry is doing the thinking. It thinks in angles and impact.",
                "Time is wrong. Everything moves slowly except you.",
            ],
        },
        "comedown": {
            "duration_seconds": 900,
            "stat_debuffs": {"agility": -15, "endurance": -15, "strength": -10, "intelligence": -5},
            "echo_comedown": [
                "The crash hits like a wall. Your legs buckle. Your vision tunnels.",
                "Vomiting. Shakes. Your heart is pounding wrong — arrhythmic, stuttering.",
                "Convulsions. Your muscles are paying for what the drug forced them to do.",
                "You can barely stand. Everything costs effort. Breathing is a project.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.35,
            "tolerance_rate": 0.15,
            "withdrawal_debuffs": {"agility": -12, "endurance": -12, "strength": -8},
            "withdrawal_echoes": [
                "You feel slow. Fragile. Mortal. You remember being invincible. The memory hurts.",
            ],
        },
        "overdose_threshold": 2,
        "drug_category": "combat_stim",
    },
    "stayup": {
        "key": "stayup",
        "name": "Stayup",
        "desc": "A white analgesic pill stamped with an upward arrow. Keeps you conscious when your body wants to quit.",
        "form": "tablet",
        "color": "white",
        "recipe": {
            "chemicals": {"ichor": 0.1, "sanguine": 0.1, "iron_salt": 0.2, "prima_materia": 0.2},
            "base_yield": 5,
            "brew_station": "synthesis",
        },
        "stages": [
            {"name": "Mixing", "duration_seconds": 180, "tend_action": "stir", "tend_desc": "A simple mix. The ichor and sanguine combine in an iron-salt matrix.", "skill_check_difficulty": 10, "quality_impact_success": 0, "quality_impact_fail": -12, "quality_impact_crit": 5},
            {"name": "Pressing", "duration_seconds": 120, "tend_action": "press", "tend_desc": "Pressed into tablets. Each one stamped with an arrow. Up.", "skill_check_difficulty": 8, "quality_impact_success": 0, "quality_impact_fail": -8, "quality_impact_crit": 3},
        ],
        "effects": {
            "duration_seconds": 600,
            "stat_buffs": {"agility": 8, "endurance": 10},
            "stat_debuffs": {"perception": -8},
            "special": ["pain_suppression", "consciousness_sustain"],
            "echo_onset": [
                "The pill dissolves. Your heart kicks. The fatigue recedes like a lie being retracted.",
                "You can keep going. Your body disagrees but your body has been overruled.",
            ],
            "echo_active": [
                "Your heartbeat is too fast. Your breathing too shallow. You don't care. You're up.",
            ],
        },
        "comedown": {
            "duration_seconds": 480,
            "stat_debuffs": {"endurance": -8, "agility": -5},
            "echo_comedown": [
                "Headache. Deep, throbbing, behind the eyes. Your heart rate won't settle.",
                "Hot flashes. Anxiety spikes. The caffeine-crash of a generation.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.15,
            "tolerance_rate": 0.08,
            "withdrawal_debuffs": {"endurance": -8},
            "withdrawal_echoes": [
                "Tired. Bone-deep tired. The kind of tired the pill was designed to mask.",
            ],
        },
        "overdose_threshold": 3,
        "drug_category": "analgesic",
    },
    "ironlung": {
        "key": "ironlung",
        "name": "Ironlung",
        "desc": "A chalky grey tablet sold at every corner stall. Keeps you working. Keeps you spending.",
        "form": "tablet",
        "color": "grey",
        "recipe": {
            "chemicals": {"iron_salt": 0.2, "ferment": 0.1, "prima_materia": 0.3},
            "base_yield": 8,
            "brew_station": "synthesis",
        },
        "stages": [
            {"name": "Dissolution", "duration_seconds": 120, "tend_action": "stir", "tend_desc": "Simple brew. Iron salt into ferment. The mixture turns grey.", "skill_check_difficulty": 6, "quality_impact_success": 0, "quality_impact_fail": -8, "quality_impact_crit": 3},
            {"name": "Pressing", "duration_seconds": 60, "tend_action": "press", "tend_desc": "Tablet press. Chalky, functional, unremarkable.", "skill_check_difficulty": 4, "quality_impact_success": 0, "quality_impact_fail": -5, "quality_impact_crit": 2},
        ],
        "effects": {
            "duration_seconds": 1200,
            "stat_buffs": {},
            "stat_debuffs": {},
            "special": ["stamina_regen_boost"],
            "echo_onset": [
                "Chalky. Bitter. You feel a slow warmth in your chest. Second wind.",
            ],
            "echo_active": [],
        },
        "comedown": {
            "duration_seconds": 120,
            "stat_debuffs": {},
            "echo_comedown": [
                "The warmth fades. Back to normal. Barely noticeable.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.12,
            "tolerance_rate": 0.05,
            "withdrawal_debuffs": {},
            "withdrawal_echoes": [
                "You feel sluggish without your Ironlung. The body adapts to the crutch.",
            ],
        },
        "overdose_threshold": 4,
        "drug_category": "utility",
    },
    "clearwater": {
        "key": "clearwater",
        "name": "Clearwater",
        "desc": "A small bottle of chalky liquid. Flushes alcohol toxins. Tastes like regret and chalk.",
        "form": "liquid",
        "color": "milky white",
        "recipe": {
            "chemicals": {"vitriol_salt": 0.2, "prima_materia": 0.4},
            "base_yield": 6,
            "brew_station": "synthesis",
        },
        "stages": [
            {"name": "Mixing", "duration_seconds": 60, "tend_action": "stir", "tend_desc": "Vitriol salt into clean prima materia. Stir. Done. Simplest thing you'll ever brew.", "skill_check_difficulty": 4, "quality_impact_success": 0, "quality_impact_fail": -5, "quality_impact_crit": 2},
        ],
        "effects": {
            "duration_seconds": 300,
            "stat_buffs": {},
            "stat_debuffs": {},
            "special": ["flush_alcohol"],
            "echo_onset": [
                "Chalky, horrible, effective. Your stomach lurches. The fog lifts. Mostly.",
            ],
            "echo_active": [],
        },
        "comedown": {
            "duration_seconds": 0,
            "stat_debuffs": {},
            "echo_comedown": [],
        },
        "addiction": {
            "addiction_rate": 0.0,
            "tolerance_rate": 0.0,
            "withdrawal_debuffs": {},
            "withdrawal_echoes": [],
        },
        "overdose_threshold": 99,
        "drug_category": "utility",
    },
    "nigredo": {
        "key": "nigredo",
        "name": "Nigredo",
        "desc": "A vial of liquid that absorbs light. It doesn't slosh — it moves. The alchemist's masterwork. The abyss, distilled.",
        "form": "liquid",
        "color": "black",
        "recipe": {
            "chemicals": {"nigredo_salt": 0.5, "anima": 0.3, "alkahest": 0.2},
            "base_yield": 1,
            "brew_station": "synthesis",
        },
        "stages": [
            {"name": "Containment", "duration_seconds": 600, "tend_action": "observe", "tend_desc": "The nigredo salt resists containment. You watch it press against the glass. It knows you're there.", "skill_check_difficulty": 24, "quality_impact_success": 0, "quality_impact_fail": -30, "quality_impact_crit": 15},
            {"name": "Binding", "duration_seconds": 900, "tend_action": "stir", "tend_desc": "You force the anima into the black salt. The mixture screams — not audibly. In your teeth.", "skill_check_difficulty": 26, "quality_impact_success": 0, "quality_impact_fail": -30, "quality_impact_crit": 15},
            {"name": "Stabilization", "duration_seconds": 600, "tend_action": "cool", "tend_desc": "The alkahest coats the mixture. It stops moving. It settles. It waits.", "skill_check_difficulty": 28, "quality_impact_success": 0, "quality_impact_fail": -35, "quality_impact_crit": 15},
            {"name": "Sealing", "duration_seconds": 300, "tend_action": "decant", "tend_desc": "Into a vial. Seal it. Don't look at it too long.", "skill_check_difficulty": 20, "quality_impact_success": 0, "quality_impact_fail": -20, "quality_impact_crit": 10},
        ],
        "effects": {
            "duration_seconds": 300,
            "stat_buffs": {"perception": 25, "intelligence": 25, "agility": 15},
            "stat_debuffs": {},
            "special": ["void_sight", "hallucination_severe", "cyberpsychosis_spike"],
            "echo_onset": [
                "|xThe liquid goes down like nothing. Because it is nothing. Because nothing is what it's made of.|n",
                "|xYou can see |Reverything|x. The structure beneath the surface. The code beneath the structure. The void beneath the code.|n",
                "|RYour chrome screams.|n Your nerves fire in patterns that aren't in any manual. You understand things. You don't want to understand them.",
            ],
            "echo_active": [
                "|xThe world is a thin skin over something deeper. You can see through it. You wish you couldn't.|n",
                "|RYour chrome is talking. Not to you. To something else.|n",
            ],
        },
        "comedown": {
            "duration_seconds": 1200,
            "stat_debuffs": {"perception": -15, "intelligence": -15, "endurance": -10},
            "echo_comedown": [
                "|xThe void recedes. It takes something with it. You can't tell what's missing.|n",
                "|RYour chrome is quiet again. You check it. It's fine. You check again. You keep checking.|n",
                "You forget what you saw. You remember that you saw something. The memory of knowledge without the knowledge itself.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.40,
            "tolerance_rate": 0.0,
            "withdrawal_debuffs": {"perception": -15, "intelligence": -10},
            "withdrawal_echoes": [
                "You can't see anymore. Not the way you could. The world is opaque again and you hate it.",
                "Your chrome whispers. Or maybe that's the absence of what the void was saying through it.",
            ],
        },
        "overdose_threshold": 1,
        "drug_category": "exotic",
    },
    "panacea": {
        "key": "panacea",
        "name": "Panacea",
        "desc": "A small vial of golden liquid. Accelerates natural healing. The closest thing the undercity has to a miracle.",
        "form": "liquid",
        "color": "golden",
        "recipe": {
            "chemicals": {"alkahest": 0.4, "sanguine": 0.2, "prima_materia": 0.2},
            "base_yield": 2,
            "brew_station": "apothecary",
        },
        "stages": [
            {"name": "Activation", "duration_seconds": 480, "tend_action": "heat", "tend_desc": "You warm the alkahest slowly. The growth factors activate. The liquid turns gold.", "skill_check_difficulty": 20, "quality_impact_success": 0, "quality_impact_fail": -25, "quality_impact_crit": 10},
            {"name": "Fortification", "duration_seconds": 360, "tend_action": "stir", "tend_desc": "The sanguine enriches the brew. Oxygen carriers for the healing tissue.", "skill_check_difficulty": 18, "quality_impact_success": 0, "quality_impact_fail": -20, "quality_impact_crit": 8},
            {"name": "Bottling", "duration_seconds": 120, "tend_action": "decant", "tend_desc": "Into vials. Two precious doses. Handle like the miracle they are.", "skill_check_difficulty": 12, "quality_impact_success": 0, "quality_impact_fail": -10, "quality_impact_crit": 5},
        ],
        "effects": {
            "duration_seconds": 1800,
            "stat_buffs": {"endurance": 5},
            "stat_debuffs": {},
            "special": ["regen_boost_major", "infection_resistance"],
            "echo_onset": [
                "Warmth. Deep, cellular warmth. Your wounds itch — not pain. Growth.",
                "You can feel yourself healing. Tissue knitting. Bruises fading. The body rebuilding.",
            ],
            "echo_active": [
                "The healing continues. Slow, steady, insistent. Your body is working overtime.",
            ],
        },
        "comedown": {
            "duration_seconds": 300,
            "stat_debuffs": {"endurance": -5},
            "echo_comedown": [
                "The warmth fades. The healing slows to normal. You feel drained. The body paid for the miracle in energy.",
            ],
        },
        "addiction": {
            "addiction_rate": 0.05,
            "tolerance_rate": 0.05,
            "withdrawal_debuffs": {},
            "withdrawal_echoes": [],
        },
        "overdose_threshold": 3,
        "drug_category": "medical",
    },
}
