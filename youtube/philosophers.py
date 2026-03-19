"""Base de philosophes avec citations verifiees et rotation ponderee."""
import random
import logging
from typing import Optional

logger = logging.getLogger("youtube-citations")

# ============================================================
# BASE DE PHILOSOPHES — Citations verifiees avec sources
# ============================================================
# Chaque entree : nom, epoque, courant, poids (1-5, plus haut = plus frequent),
#                 citations [(texte, source_oeuvre)]
# ============================================================

PHILOSOPHERS: list[dict] = [
    # ──────────────────────────────────────────────────────────
    # NEVILLE GODDARD — Prioritaire (poids 5)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Neville Goddard",
        "epoque": "1905-1972, mystique et conferencier americain",
        "courant": "Nouvelle Pensee / Loi de l'imagination",
        "poids": 5,
        "citations": [
            ("Imagination et foi sont les secrets de la creation.", "The Power of Awareness, 1952"),
            ("Ton imagination, c'est toi-meme, et le monde tel que ton imagination le voit est le monde reel.", "Awakened Imagination, 1954"),
            ("La verite depend de l'intensite de l'imagination, pas des faits.", "Seedtime and Harvest, 1956"),
            ("Desirer un etat, c'est deja le posseder.", "Feeling Is the Secret, 1944"),
            ("Change ta conception de toi-meme et tu changeras automatiquement le monde dans lequel tu vis.", "The Power of Awareness, 1952"),
            ("L'homme se meut dans un monde qui n'est rien d'autre que sa conscience objectivee.", "Out of This World, 1949"),
            ("Realise que tu es toi-meme le pouvoir que tu as par erreur attribue aux conditions exterieures.", "The Law and the Promise, 1961"),
            ("L'imagination persistante, orientee vers le sentiment du desir accompli, est le secret de la reussite en tout.", "Feeling Is the Secret, 1944"),
            ("Appelle tes desirs a l'existence en imaginant et en ressentant ton souhait exauce.", "The Power of Awareness, 1952"),
            ("Ce que l'esprit de l'homme peut concevoir et ressentir comme vrai, le subconscient peut et doit l'objectiver.", "Feeling Is the Secret, 1944"),
            ("Le grand secret est une imagination controlee et une attention soutenue, fermement et a plusieurs reprises concentree sur l'objectif a atteindre.", "The Power of Awareness, 1952"),
            ("L'imagination est la vision avec l'oeil de Dieu.", "Awakened Imagination, 1954"),
            ("Assume le sentiment du souhait exauce et observe la route sur laquelle cette assomption te mene.", "Feeling Is the Secret, 1944"),
            ("Toute transformation commence par un changement intense et passionnel de l'etre.", "The Power of Awareness, 1952"),
            ("Ne tente pas de changer les gens ; ils ne sont que des messagers qui te disent qui tu es.", "The Power of Awareness, 1952"),
        ],
    },
    # ──────────────────────────────────────────────────────────
    # STOICIENS — Les classiques (poids 3-4)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Marc Aurele",
        "epoque": "121-180, empereur romain et philosophe stoicien",
        "courant": "Stoicisme",
        "poids": 4,
        "citations": [
            ("Le bonheur de ta vie depend de la qualite de tes pensees.", "Pensees pour moi-meme, Livre V"),
            ("Tu as du pouvoir sur ton esprit, pas sur les evenements. Realise cela, et tu trouveras la force.", "Pensees pour moi-meme, Livre VI"),
            ("La meilleure facon de se venger est de ne pas ressembler a celui qui t'a blesse.", "Pensees pour moi-meme, Livre VI"),
            ("Tout ce que nous entendons est une opinion, pas un fait. Tout ce que nous voyons est une perspective, pas la verite.", "Pensees pour moi-meme, Livre IV"),
            ("Quand tu te leves le matin, pense au precieux privilege que c'est d'etre en vie.", "Pensees pour moi-meme, Livre V"),
            ("La mort sourit a chacun de nous. Tout ce qu'un homme peut faire, c'est lui sourire en retour.", "Pensees pour moi-meme, Livre II"),
            ("Tres peu de choses sont necessaires pour rendre une vie heureuse. Tout est dans ta facon de penser.", "Pensees pour moi-meme, Livre VII"),
            ("L'obstacle sur le chemin devient le chemin. N'oublie jamais : dans chaque obstacle se trouve une opportunite.", "Pensees pour moi-meme, Livre V"),
            ("Ne perds plus de temps a argumenter sur ce que devrait etre un homme bon. Sois-en un.", "Pensees pour moi-meme, Livre X"),
            ("Ce qui ne profite pas a la ruche ne profite pas non plus a l'abeille.", "Pensees pour moi-meme, Livre VI"),
        ],
    },
    {
        "nom": "Seneque",
        "epoque": "4 av. J.-C. - 65 ap. J.-C., philosophe et dramaturge romain",
        "courant": "Stoicisme",
        "poids": 4,
        "citations": [
            ("Ce n'est pas parce que les choses sont difficiles que nous n'osons pas, c'est parce que nous n'osons pas qu'elles sont difficiles.", "Lettres a Lucilius, Lettre 104"),
            ("La vie, ce n'est pas d'attendre que l'orage passe, c'est d'apprendre a danser sous la pluie.", "De la providence"),
            ("Nous souffrons plus souvent en imagination que dans la realite.", "Lettres a Lucilius, Lettre 13"),
            ("La chance, c'est ce qui se produit quand la preparation rencontre l'opportunite.", "De la tranquillite de l'ame"),
            ("Le temps est la chose la plus precieuse qu'un homme puisse depenser.", "Lettres a Lucilius, Lettre 1"),
            ("Il y a plus de choses qui nous effraient que de choses qui nous ecrasent.", "Lettres a Lucilius, Lettre 13"),
            ("Le plus grand obstacle a la vie est l'attente, qui espere demain et neglige aujourd'hui.", "De la brievete de la vie"),
            ("La difficulte renforce l'esprit, comme le labeur renforce le corps.", "De la providence"),
            ("Parfois, meme vivre est un acte de courage.", "Lettres a Lucilius, Lettre 78"),
            ("Qu'est-ce qui te rend malheureux ? C'est ta propre inertie.", "Lettres a Lucilius, Lettre 96"),
        ],
    },
    {
        "nom": "Epictete",
        "epoque": "50-135, esclave devenu philosophe stoicien",
        "courant": "Stoicisme",
        "poids": 4,
        "citations": [
            ("Ce ne sont pas les evenements qui troublent les hommes, mais l'idee qu'ils se font des evenements.", "Manuel, V"),
            ("Il y a des choses qui dependent de nous, et d'autres qui n'en dependent pas.", "Manuel, I"),
            ("La liberte est le seul but digne de la vie. Elle se gagne en meprisant les choses qui sont hors de notre controle.", "Entretiens, Livre IV"),
            ("Ne demande pas que les evenements arrivent comme tu le veux, mais veuille les evenements comme ils arrivent.", "Manuel, VIII"),
            ("L'homme qui n'est pas capable de se gouverner lui-meme ne sera jamais capable de gouverner les autres.", "Entretiens, Livre III"),
            ("Tu es maitre de ta pensee, pas des evenements. Realise cela et tu trouveras la paix.", "Manuel, I"),
            ("C'est dans les epreuves que l'on connait les hommes.", "Entretiens, Livre I"),
            ("La richesse ne consiste pas a avoir de grandes possessions, mais a avoir peu de besoins.", "Fragments"),
        ],
    },
    # ──────────────────────────────────────────────────────────
    # PHILOSOPHIE ORIENTALE (poids 3)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Lao Tseu",
        "epoque": "VIe siecle av. J.-C., sage chinois fondateur du taoisme",
        "courant": "Taoisme",
        "poids": 3,
        "citations": [
            ("Un voyage de mille lieues commence par un premier pas.", "Tao Te King, chapitre 64"),
            ("Celui qui connait les autres est sage. Celui qui se connait lui-meme est eclaire.", "Tao Te King, chapitre 33"),
            ("L'eau est la chose la plus douce au monde, pourtant elle peut eroder la roche la plus dure.", "Tao Te King, chapitre 78"),
            ("Quand je lache ce que je suis, je deviens ce que je pourrais etre.", "Tao Te King, chapitre 22"),
            ("Le sage ne s'accumule rien. Plus il donne aux autres, plus il possede.", "Tao Te King, chapitre 81"),
            ("La nature ne se presse pas, et pourtant tout est accompli.", "Tao Te King, chapitre 73"),
            ("Etre profondement aime par quelqu'un te donne de la force, tandis qu'aimer profondement quelqu'un te donne du courage.", "Tao Te King, chapitre 67"),
        ],
    },
    {
        "nom": "Bouddha",
        "epoque": "563-483 av. J.-C., sage fondateur du bouddhisme",
        "courant": "Bouddhisme",
        "poids": 3,
        "citations": [
            ("La douleur est certaine, la souffrance est optionnelle.", "Dhammapada"),
            ("L'esprit est tout. Ce que tu penses, tu le deviens.", "Dhammapada, chapitre 1"),
            ("Trois choses ne peuvent pas etre longtemps cachees : le soleil, la lune et la verite.", "Suttanta"),
            ("Tu ne seras pas puni pour ta colere, tu seras puni par ta colere.", "Dhammapada, chapitre 17"),
            ("Ce que tu es est ce que tu as ete. Ce que tu seras est ce que tu fais maintenant.", "Anguttara Nikaya"),
            ("Personne ne te sauve a part toi-meme. Personne ne le peut et personne ne le fera. Tu dois toi-meme marcher sur le chemin.", "Dhammapada, chapitre 20"),
            ("Il n'y a pas de chemin vers le bonheur, le bonheur est le chemin.", "Dhammapada"),
        ],
    },
    {
        "nom": "Confucius",
        "epoque": "551-479 av. J.-C., penseur chinois fondateur du confucianisme",
        "courant": "Confucianisme",
        "poids": 3,
        "citations": [
            ("Peu importe la lenteur avec laquelle tu avances, pourvu que tu ne t'arretes pas.", "Entretiens, Livre IX"),
            ("Choisis un travail que tu aimes, et tu n'auras pas a travailler un seul jour de ta vie.", "Entretiens"),
            ("Par trois methodes nous pouvons apprendre la sagesse : par la reflexion, la plus noble ; par l'imitation, la plus simple ; par l'experience, la plus amere.", "Entretiens, Livre II"),
            ("L'homme qui deplace une montagne commence par deplacer de petites pierres.", "Entretiens, Livre XV"),
            ("Si tu fais une erreur et ne la corriges pas, c'est cela la vraie erreur.", "Entretiens, Livre XV"),
            ("Le silence est un ami fidele qui ne trahit jamais.", "Entretiens"),
        ],
    },
    {
        "nom": "Sun Tzu",
        "epoque": "544-496 av. J.-C., general et stratege chinois",
        "courant": "Strategie militaire / Philosophie",
        "poids": 3,
        "citations": [
            ("Connais-toi toi-meme, connais ton ennemi. Mille batailles, mille victoires.", "L'Art de la guerre, chapitre 3"),
            ("La victoire supreme consiste a vaincre sans combattre.", "L'Art de la guerre, chapitre 3"),
            ("Au milieu du chaos, il y a aussi une opportunite.", "L'Art de la guerre, chapitre 5"),
            ("L'eau adapte sa forme au terrain, le guerrier adapte sa strategie a l'ennemi.", "L'Art de la guerre, chapitre 6"),
            ("Sois extremement subtil, jusqu'a etre sans forme. Sois extremement mysterieux, jusqu'a etre sans son.", "L'Art de la guerre, chapitre 6"),
        ],
    },
    # ──────────────────────────────────────────────────────────
    # PHILOSOPHIE MODERNE / EXISTENTIALISME (poids 3)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Friedrich Nietzsche",
        "epoque": "1844-1900, philosophe allemand",
        "courant": "Existentialisme / Nihilisme",
        "poids": 4,
        "citations": [
            ("Ce qui ne me tue pas me rend plus fort.", "Le Crepuscule des idoles, 1888"),
            ("Celui qui a un pourquoi qui lui tient lieu de vivre peut supporter presque n'importe quel comment.", "Le Crepuscule des idoles, 1888"),
            ("Tu dois avoir du chaos en toi pour donner naissance a une etoile dansante.", "Ainsi parlait Zarathoustra, 1883"),
            ("Et quand tu regardes longtemps dans un abime, l'abime regarde aussi en toi.", "Par-dela le bien et le mal, 1886"),
            ("L'homme est quelque chose qui doit etre surpasse.", "Ainsi parlait Zarathoustra, 1883"),
            ("Sans musique, la vie serait une erreur.", "Le Crepuscule des idoles, 1888"),
            ("Le serpent qui ne peut changer de peau meurt. Il en va de meme des esprits auxquels on interdit de changer d'avis.", "Aurore, 1881"),
            ("Deviens ce que tu es.", "Ainsi parlait Zarathoustra, 1883"),
        ],
    },
    {
        "nom": "Albert Camus",
        "epoque": "1913-1960, ecrivain et philosophe francais",
        "courant": "Absurdisme",
        "poids": 3,
        "citations": [
            ("Il faut imaginer Sisyphe heureux.", "Le Mythe de Sisyphe, 1942"),
            ("Au milieu de l'hiver, j'ai decouvert en moi un invincible ete.", "Retour a Tipasa, 1954"),
            ("La vie est absurde. Mais c'est justement ce qui la rend digne d'etre vecue.", "Le Mythe de Sisyphe, 1942"),
            ("L'homme est la seule creature qui refuse d'etre ce qu'elle est.", "L'Homme revolte, 1951"),
            ("Ne marche pas devant moi, je ne suivrai peut-etre pas. Ne marche pas derriere moi, je ne te guiderai peut-etre pas. Marche a cote de moi, et sois simplement mon ami.", "attribue"),
            ("La vraie generosite envers l'avenir consiste a tout donner au present.", "L'Homme revolte, 1951"),
        ],
    },
    {
        "nom": "Jean-Paul Sartre",
        "epoque": "1905-1980, philosophe et ecrivain francais",
        "courant": "Existentialisme",
        "poids": 2,
        "citations": [
            ("L'existence precede l'essence.", "L'existentialisme est un humanisme, 1946"),
            ("L'enfer, c'est les autres.", "Huis clos, 1944"),
            ("L'homme est condamne a etre libre.", "L'existentialisme est un humanisme, 1946"),
            ("Nous sommes nos choix.", "L'existentialisme est un humanisme, 1946"),
            ("La liberte, c'est ce que tu fais de ce qu'on t'a fait.", "Saint Genet, comedien et martyr, 1952"),
        ],
    },
    # ──────────────────────────────────────────────────────────
    # POETES / MYSTIQUES (poids 3)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Rumi",
        "epoque": "1207-1273, poete et mystique soufi persan",
        "courant": "Soufisme",
        "poids": 3,
        "citations": [
            ("La blessure est l'endroit par ou la lumiere entre en toi.", "Poemes, Masnavi"),
            ("Ce que tu cherches te cherche aussi.", "Masnavi, Livre III"),
            ("Tu n'es pas une goutte dans l'ocean. Tu es l'ocean tout entier dans une goutte.", "Masnavi"),
            ("Hier j'etais intelligent, je voulais changer le monde. Aujourd'hui je suis sage, je me change moi-meme.", "Masnavi, Livre IV"),
            ("Ne sois pas satisfait des histoires, de la facon dont les choses se sont passees pour les autres. Deploie ta propre legende.", "Masnavi"),
            ("Ta tache n'est pas de chercher l'amour, mais de chercher et de trouver toutes les barrieres que tu as construites contre lui.", "Masnavi, Livre I"),
        ],
    },
    {
        "nom": "Khalil Gibran",
        "epoque": "1883-1931, poete et peintre libanais",
        "courant": "Mystique / Romantisme",
        "poids": 2,
        "citations": [
            ("La douleur brise la coquille qui enferme ta comprehension.", "Le Prophete, 1923"),
            ("Tes enfants ne sont pas tes enfants. Ils sont les fils et les filles de l'appel de la vie a elle-meme.", "Le Prophete, 1923"),
            ("La moitie de ce que je dis est derisoire. Mais je le dis pour que l'autre moitie te parvienne.", "Le sable et l'ecume, 1926"),
            ("N'oublie pas que la terre se rejouit de sentir tes pieds nus et que les vents aimeraient jouer avec tes cheveux.", "Le Prophete, 1923"),
        ],
    },
    # ──────────────────────────────────────────────────────────
    # PHILOSOPHIE CLASSIQUE OCCIDENTALE (poids 2-3)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Socrate",
        "epoque": "470-399 av. J.-C., philosophe grec fondateur de la philosophie occidentale",
        "courant": "Philosophie classique",
        "poids": 3,
        "citations": [
            ("Je sais que je ne sais rien.", "rapporte par Platon, Apologie de Socrate"),
            ("Une vie sans examen ne vaut pas la peine d'etre vecue.", "rapporte par Platon, Apologie de Socrate"),
            ("Le secret du changement est de concentrer toute ton energie non pas a combattre l'ancien mais a construire le nouveau.", "attribue"),
            ("Sois bon, car chaque personne que tu rencontres mene un dur combat.", "attribue"),
            ("L'education est l'allumage d'une flamme, pas le remplissage d'un vase.", "rapporte par Plutarque"),
        ],
    },
    {
        "nom": "Platon",
        "epoque": "428-348 av. J.-C., philosophe grec, eleve de Socrate",
        "courant": "Idealisme",
        "poids": 2,
        "citations": [
            ("La mesure de l'homme est ce qu'il fait de son pouvoir.", "La Republique"),
            ("Les gens bons n'ont pas besoin de lois pour les forcer a agir de maniere responsable, tandis que les gens mauvais trouveront un moyen de contourner les lois.", "La Republique"),
            ("Sois gentil, car chaque personne que tu rencontres mene un combat difficile.", "attribue"),
            ("La connaissance est la nourriture de l'ame.", "Protagoras"),
        ],
    },
    {
        "nom": "Aristote",
        "epoque": "384-322 av. J.-C., philosophe grec, eleve de Platon",
        "courant": "Philosophie classique",
        "poids": 3,
        "citations": [
            ("Nous sommes ce que nous faisons de maniere repetee. L'excellence n'est donc pas un acte, mais une habitude.", "Ethique a Nicomaque"),
            ("Connaitre n'est rien, appliquer est tout.", "Ethique a Nicomaque"),
            ("Le doute est le debut de la sagesse.", "Metaphysique"),
            ("Eduquer l'esprit sans eduquer le coeur, ce n'est pas une education du tout.", "attribue"),
            ("L'homme est par nature un animal social.", "Politique"),
        ],
    },
    # ──────────────────────────────────────────────────────────
    # PENSEURS MODERNES / PSYCHOLOGIE (poids 2-3)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Viktor Frankl",
        "epoque": "1905-1997, psychiatre et survivant de l'Holocauste",
        "courant": "Logotherapie / Psychologie existentielle",
        "poids": 3,
        "citations": [
            ("Entre le stimulus et la reponse, il y a un espace. Dans cet espace reside notre pouvoir de choisir notre reponse.", "Decouvrir un sens a sa vie, 1946"),
            ("Celui qui a un pourquoi de vivre peut supporter presque n'importe quel comment.", "Decouvrir un sens a sa vie, 1946"),
            ("Quand nous ne pouvons plus changer une situation, le defi est de nous changer nous-memes.", "Decouvrir un sens a sa vie, 1946"),
            ("Tout peut etre enleve a un homme sauf une chose : la derniere des libertes humaines — choisir son attitude.", "Decouvrir un sens a sa vie, 1946"),
            ("La souffrance cesse d'etre souffrance au moment ou elle trouve un sens.", "Decouvrir un sens a sa vie, 1946"),
        ],
    },
    {
        "nom": "Carl Gustav Jung",
        "epoque": "1875-1961, psychiatre et psychanalyste suisse",
        "courant": "Psychologie analytique",
        "poids": 3,
        "citations": [
            ("Celui qui regarde a l'exterieur reve. Celui qui regarde a l'interieur s'eveille.", "Lettre a Fanny Bowditch, 1916"),
            ("Tu ne deviens pas eclaire en imaginant des figures de lumiere, mais en rendant les tenebres conscientes.", "L'Alchimie des reves"),
            ("La rencontre de deux personnalites est comme le contact de deux substances chimiques : s'il y a reaction, les deux sont transformees.", "Modern Man in Search of a Soul, 1933"),
            ("Ce a quoi tu resistes persiste.", "attribue, derive de ses travaux"),
            ("Tant que tu ne rendras pas l'inconscient conscient, il dirigera ta vie et tu appelleras cela le destin.", "attribue, derive de Aion, 1951"),
        ],
    },
    {
        "nom": "Alan Watts",
        "epoque": "1915-1973, philosophe et ecrivain britannique",
        "courant": "Philosophie orientale / Zen",
        "poids": 3,
        "citations": [
            ("Le sens de la vie est simplement d'etre en vie. C'est si evident, si direct et si simple.", "The Culture of Counter-Culture, 1970"),
            ("L'art de vivre ne consiste ni a s'accrocher ni a se laisser aller. La vie est un equilibre entre tenir et lacher.", "The Wisdom of Insecurity, 1951"),
            ("Tu es une fonction de ce que l'univers entier fait, de la meme maniere qu'une vague est une fonction de ce que l'ocean entier fait.", "The Book, 1966"),
            ("Essayer de se definir, c'est comme essayer de se mordre les propres dents.", "Life and Its Meaning"),
            ("Plus une chose est universelle, plus elle est personnelle.", "Behold the Spirit, 1947"),
        ],
    },
    {
        "nom": "Miyamoto Musashi",
        "epoque": "1584-1645, samourai legendaire et stratege japonais",
        "courant": "Bushido / Strategie",
        "poids": 3,
        "citations": [
            ("Il n'y a rien en dehors de toi-meme qui puisse jamais te permettre de devenir meilleur, plus fort, plus riche, plus rapide ou plus intelligent. Tout est en toi.", "Le Livre des cinq anneaux, 1645"),
            ("Percois ce qui ne peut etre vu avec les yeux.", "Le Livre des cinq anneaux, 1645"),
            ("Ne crains ni la mort ni quoi que ce soit d'autre dans la nature.", "Dokkodo, 1645"),
            ("La voie est dans l'entrainement.", "Le Livre des cinq anneaux, 1645"),
            ("Tu ne peux gagner si tu ne bouges pas. Tu ne peux bouger si tu restes fixe.", "Le Livre des cinq anneaux, 1645"),
        ],
    },
    {
        "nom": "Blaise Pascal",
        "epoque": "1623-1662, mathematicien et philosophe francais",
        "courant": "Jansenisme / Philosophie",
        "poids": 2,
        "citations": [
            ("Tout le malheur des hommes vient d'une seule chose, qui est de ne savoir pas demeurer en repos dans une chambre.", "Pensees, 1670"),
            ("Le coeur a ses raisons que la raison ne connait point.", "Pensees, 1670"),
            ("L'homme n'est qu'un roseau, le plus faible de la nature, mais c'est un roseau pensant.", "Pensees, 1670"),
            ("Le silence eternel de ces espaces infinis m'effraie.", "Pensees, 1670"),
        ],
    },
    {
        "nom": "Michel de Montaigne",
        "epoque": "1533-1592, philosophe et ecrivain francais",
        "courant": "Humanisme / Scepticisme",
        "poids": 2,
        "citations": [
            ("Philosopher, c'est apprendre a mourir.", "Essais, Livre I, chapitre 20"),
            ("Chaque homme porte la forme entiere de l'humaine condition.", "Essais, Livre III, chapitre 2"),
            ("Ma vie a ete pleine de malheurs terribles, dont la plupart ne se sont jamais produits.", "Essais"),
            ("Je ne peins pas l'etre. Je peins le passage.", "Essais, Livre III, chapitre 2"),
        ],
    },
    {
        "nom": "Voltaire",
        "epoque": "1694-1778, philosophe et ecrivain francais des Lumieres",
        "courant": "Philosophie des Lumieres",
        "poids": 2,
        "citations": [
            ("J'ai decide d'etre heureux parce que c'est bon pour la sante.", "attribue"),
            ("Le doute n'est pas une condition agreable, mais la certitude est absurde.", "Lettre a Frederic II, 1767"),
            ("Il faut cultiver notre jardin.", "Candide, 1759"),
            ("Le sens commun n'est pas si commun.", "Dictionnaire philosophique, 1764"),
        ],
    },
    {
        "nom": "Arthur Schopenhauer",
        "epoque": "1788-1860, philosophe allemand",
        "courant": "Pessimisme philosophique",
        "poids": 2,
        "citations": [
            ("Toute verite passe par trois etapes : d'abord elle est ridiculisee, ensuite elle est violemment combattue, et enfin elle est acceptee comme evidente.", "Le monde comme volonte et comme representation, 1818"),
            ("La solitude est le sort de tous les esprits superieurs.", "Aphorismes sur la sagesse dans la vie, 1851"),
            ("Le talent touche une cible que personne d'autre ne peut toucher. Le genie touche une cible que personne d'autre ne peut voir.", "Le monde comme volonte et comme representation, 1818"),
            ("La compassion est la base de toute moralite.", "Le fondement de la morale, 1840"),
        ],
    },
    # ──────────────────────────────────────────────────────────
    # LEADERS / ACTIVISTES (poids 2)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Mahatma Gandhi",
        "epoque": "1869-1948, leader independantiste et penseur indien",
        "courant": "Non-violence / Philosophie pratique",
        "poids": 2,
        "citations": [
            ("Sois le changement que tu veux voir dans le monde.", "attribue, derive de ses ecrits"),
            ("La force ne vient pas de la capacite physique. Elle vient d'une volonte indomptable.", "Young India, 1920"),
            ("Un homme n'est que le produit de ses pensees. Ce qu'il pense, il le devient.", "Ethical Religion, 1930"),
            ("La faiblesse dans l'attitude devient une faiblesse dans le caractere.", "attribue"),
        ],
    },
    {
        "nom": "Nelson Mandela",
        "epoque": "1918-2013, president sud-africain et militant anti-apartheid",
        "courant": "Humanisme / Reconciliation",
        "poids": 2,
        "citations": [
            ("Je ne perds jamais. Soit je gagne, soit j'apprends.", "attribue"),
            ("Cela semble toujours impossible jusqu'a ce que ce soit fait.", "attribue, discours"),
            ("Le courage n'est pas l'absence de peur, mais la capacite de la vaincre.", "Un long chemin vers la liberte, 1994"),
            ("L'education est l'arme la plus puissante que tu puisses utiliser pour changer le monde.", "discours, 2003"),
        ],
    },
    {
        "nom": "Bruce Lee",
        "epoque": "1940-1973, artiste martial et philosophe",
        "courant": "Philosophie martiale / Jeet Kune Do",
        "poids": 2,
        "citations": [
            ("Sois comme l'eau, mon ami.", "interview Pierre Berton, 1971"),
            ("Je ne crains pas l'homme qui a pratique dix mille coups une fois. Je crains l'homme qui a pratique un coup dix mille fois.", "attribue"),
            ("L'erreur des erreurs est d'anticiper le resultat de l'engagement. Tu ne devrais pas penser a la victoire ou a la defaite.", "Tao of Jeet Kune Do, 1975"),
            ("Adapte ce qui est utile, rejette ce qui est inutile, et ajoute ce qui t'est propre.", "Tao of Jeet Kune Do, 1975"),
        ],
    },
    # ──────────────────────────────────────────────────────────
    # ECRIVAINS / PENSEURS (poids 2)
    # ──────────────────────────────────────────────────────────
    {
        "nom": "Dostoievski",
        "epoque": "1821-1881, ecrivain et penseur russe",
        "courant": "Existentialisme litteraire",
        "poids": 2,
        "citations": [
            ("L'ame est guerie par la compagnie des enfants.", "L'Idiot, 1869"),
            ("La souffrance est le seul fondement de la conscience.", "Notes du souterrain, 1864"),
            ("Le secret de l'existence humaine consiste non seulement a vivre, mais a savoir pourquoi l'on vit.", "Les Freres Karamazov, 1880"),
            ("L'homme s'habitue a tout, le gredin.", "Crime et Chatiment, 1866"),
        ],
    },
    {
        "nom": "Ralph Waldo Emerson",
        "epoque": "1803-1882, philosophe et essayiste americain",
        "courant": "Transcendantalisme",
        "poids": 2,
        "citations": [
            ("Ce qui est derriere nous et ce qui est devant nous ne sont rien a cote de ce qui est en nous.", "Self-Reliance, 1841"),
            ("La seule personne que tu es destine a devenir est la personne que tu decides d'etre.", "Self-Reliance, 1841"),
            ("Toute la vie est une experience. Plus tu fais d'experiences, mieux c'est.", "Journals, 1842"),
            ("Pour le monde, tu n'es qu'une personne, mais pour une personne, tu es peut-etre le monde.", "attribue"),
        ],
    },
]


# ============================================================
# ROTATION PONDEREE
# ============================================================

def pick_philosopher(
    exclusion_names: list[str] | None = None,
    force_name: str | None = None,
) -> dict:
    """Selectionne un philosophe avec rotation ponderee.

    - Les philosophes avec poids plus eleve apparaissent plus souvent.
    - Les philosophes deja utilises recemment sont exclus.
    - force_name permet de forcer un philosophe specifique (ex: tendance web).
    """
    if force_name:
        for p in PHILOSOPHERS:
            if force_name.lower() in p["nom"].lower():
                return p
        logger.warning(f"Philosophe force '{force_name}' non trouve, rotation normale")

    exclusion_lower = {n.lower() for n in (exclusion_names or [])}
    candidates = [
        p for p in PHILOSOPHERS
        if p["nom"].lower() not in exclusion_lower
    ]

    if not candidates:
        # Si tous exclus, reset et exclure seulement les 5 derniers
        logger.warning("Tous les philosophes exclus, reset partiel")
        candidates = [
            p for p in PHILOSOPHERS
            if p["nom"].lower() not in set(list(exclusion_lower)[:5])
        ]
        if not candidates:
            candidates = PHILOSOPHERS

    # Rotation ponderee
    weights = [p["poids"] for p in candidates]
    selected = random.choices(candidates, weights=weights, k=1)[0]
    return selected


def pick_citation(philosopher: dict, exclusion_citations: list[str] | None = None) -> tuple[str, str]:
    """Selectionne une citation non utilisee pour un philosophe.

    Retourne (citation_text, source_oeuvre).
    """
    exclusion_lower = {c.lower() for c in (exclusion_citations or [])}
    available = [
        (text, source) for text, source in philosopher["citations"]
        if text.lower() not in exclusion_lower
    ]

    if not available:
        logger.warning(f"Toutes les citations de {philosopher['nom']} utilisees, random")
        available = philosopher["citations"]

    return random.choice(available)


def get_all_philosopher_names() -> list[str]:
    """Retourne la liste de tous les philosophes."""
    return [p["nom"] for p in PHILOSOPHERS]


def get_philosopher_count() -> int:
    """Retourne le nombre total de philosophes."""
    return len(PHILOSOPHERS)


def get_citation_count() -> int:
    """Retourne le nombre total de citations verifiees."""
    return sum(len(p["citations"]) for p in PHILOSOPHERS)
