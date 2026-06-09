from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from library_workshops.models import Workshop, WorkshopParticipant
from visitor_tracking.models import Location as VisitorLocation
from datetime import date, time, timedelta
import random

WORKSHOP_TITLES = [
    "Scottie GO",
    "Atelier Lecture Enfants",
    "Initiation Dessin",
    "Atelier Musique",
    "Danse Contemporaine",
    "Peinture Acrylique",
    "Création BD",
    "Théâtre d'Impro",
    "Photographie Numérique",
    "Cuisine du Monde",
    "Jardinage Urbain",
    "Origami Avancé",
    "Couture Débutant",
    "Poterie Modelage",
    "Atelier Écriture",
    "Yoga Parent-Enfant",
    "Éveil Musical",
    "Arts Plastiques",
    "Robotique Junior",
    "Stop Motion",
    "Calligraphie",
    "Atelier Philo",
    "Tricot Créatif",
    "Fresque Collective",
    "Marionnettes",
    "Poterie Tour",
    "Anglais Ludique",
    "Atelier Nature",
    "Tissage Brésilien",
    "Mosaïque",
    "Création Bijoux",
    "Atelier Chant",
    "Percussions Africaines",
    "Théâtre Ombres",
    "Linogravure",
    "Aquarelle",
    "Atelier Cartes",
    "Compostage",
    "Reliure Carnet",
    "Jeux de Société Géants",
    "Atelier Récup",
    "Vannerie",
    "Création Papier",
    "Manga Débutant",
    "Atelier Masques",
    "Tapis Lecture",
    "Karaoké",
    "Atelier Bulles",
    "Herbier Créatif",
    "Bricolage Nature",
    "Atelier Sable",
    "Création Mobile",
    "Pâte Fimo",
    "Land Art",
    "Atelier Laine",
    "Perles à Repasser",
    "Tampons Créatifs",
    "Vitrail Débutant",
    "Atelier Céramique",
    "Cadres Nature",
    "Atelier Floral",
    "Bougies Déco",
    "Bijoux Résine",
    "Atelier Raku",
    "Furoshiki",
    "Teinture Végétale",
    "Kintsugi",
    "Atelier Encre",
    "Sérigraphie",
    "Diorama",
    "Cyanotype",
]

FIRST_NAMES = [
    "Emma",
    "Lucas",
    "Léa",
    "Hugo",
    "Chloé",
    "Nathan",
    "Inès",
    "Tom",
    "Louise",
    "Maxime",
    "Sarah",
    "Enzo",
    "Camille",
    "Mathis",
    "Manon",
    "Théo",
    "Jade",
    "Louis",
    "Lola",
    "Gabriel",
    "Alice",
    "Raphaël",
    "Eva",
    "Jules",
    "Zoé",
    "Gabin",
    "Anna",
    "Timéo",
    "Mila",
    "Paul",
    "Léna",
    "Noah",
    "Rose",
    "Marius",
    "Iris",
    "Oscar",
    "Nina",
    "Liam",
    "Charlie",
    "Sacha",
    "Romy",
    "Aaron",
    "Agathe",
    "Gaspard",
    "Maya",
    "Victor",
    "Olive",
    "Malo",
    "June",
    "Milo",
    "Jeanne",
    "Léon",
    "Alba",
    "Nino",
    "Adèle",
    "Isaac",
    "Rosa",
    "Naël",
    "Alix",
    "Amaury",
    "Éline",
    "Maël",
    "Lise",
    "Soan",
    "Angèle",
    "Sohan",
    "Faustine",
    "Kenji",
    "Yuna",
    "Soren",
]

LAST_NAMES = [
    "Martin",
    "Bernard",
    "Dubois",
    "Thomas",
    "Robert",
    "Richard",
    "Petit",
    "Durand",
    "Leroy",
    "Moreau",
    "Simon",
    "Laurent",
    "Lefebvre",
    "Michel",
    "Garcia",
    "David",
    "Bertrand",
    "Roux",
    "Vincent",
    "Fournier",
    "Morel",
    "Girard",
    "Andre",
    "Lefevre",
    "Mercier",
    "Dupont",
    "Lambert",
    "Bonnet",
    "Francois",
    "Martinez",
    "Legrand",
    "Garnier",
    "Faure",
    "Rousseau",
    "Blanchard",
    "Clement",
    "Morin",
    "Nicolas",
    "Henry",
    "Roussel",
    "Mathieu",
    "Gautier",
    "Masson",
    "Gauthier",
    "Chevalier",
    "Perrin",
    "Colin",
    "Brunet",
    "Schmitt",
    "Leroux",
]

AGE_RANGES = [
    (None, None, True),
    (3, 6, False),
    (7, 12, False),
    (13, 17, False),
    (18, 25, False),
    (26, 64, False),
    (60, 99, False),
    (10, 15, False),
    (0, 3, False),
    (16, 25, False),
    (55, 99, False),
    (8, 16, False),
]


def random_participants(workshop, max_count, status_weights=None):
    if status_weights is None:
        status_weights = {"confirmed": 0.7, "waiting": 0.2, "cancelled": 0.1}
    count = random.randint(0, max_count)
    statuses = list(status_weights.keys())
    weights = list(status_weights.values())
    anor = User.objects.get(username="anor")
    for _ in range(count):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        status = random.choices(statuses, weights=weights, k=1)[0]
        WorkshopParticipant.objects.create(
            workshop=workshop,
            first_name=first,
            last_name=last,
            age=random.randint(3, 85),
            email=f"{first.lower()}.{last.lower()}@email.fr",
            status=status,
            added_by=anor,
        )


def create_workshop(
    title,
    start_date,
    start_time,
    end_time=None,
    location=None,
    max_participants=15,
    is_all_ages=True,
    min_age=None,
    max_age=None,
    newsletter=True,
    is_class_welcome=False,
    reminder_sent=False,
    end_date=None,
):
    anor = User.objects.get(username="anor")
    if end_time is None:
        end_hour = start_time.hour + 2
        if end_hour >= 24:
            end_hour = 23
        end_time = time(end_hour, 0)
    if location is None:
        location = VisitorLocation.objects.filter(is_active=True).order_by("?").first()
    return Workshop.objects.create(
        title=title,
        description=f"Atelier {title} - {description_for(title)}",
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        location=location,
        max_participants=max_participants,
        is_all_ages=is_all_ages,
        min_age=min_age,
        max_age=max_age,
        newsletter=newsletter,
        is_class_welcome=is_class_welcome,
        reminder_sent=reminder_sent,
        created_by=anor,
    )


def description_for(title):
    descs = {
        "Scottie GO": "Session de découverte du jeu Scottie GO",
        "Atelier Lecture Enfants": "Séance de lecture pour enfants",
        "Initiation Dessin": "Premiers pas en dessin",
        "Atelier Musique": "Initiation aux instruments de musique",
        "Danse Contemporaine": "Cours de danse contemporaine",
        "Peinture Acrylique": "Techniques de peinture acrylique",
        "Création BD": "Création de bande dessinée",
        "Théâtre d'Impro": "Exercices d'improvisation théâtrale",
        "Photographie Numérique": "Initiation à la photographie numérique",
        "Cuisine du Monde": "Découverte des cuisines du monde",
        "Jardinage Urbain": "Techniques de jardinage en ville",
        "Origami Avancé": "Plis complexes et créations avancées",
        "Couture Débutant": "Apprentissage des bases de la couture",
        "Poterie Modelage": "Création d'objets en argile",
        "Atelier Écriture": "Exercices d'écriture créative",
        "Yoga Parent-Enfant": "Séance de yoga en duo parent-enfant",
        "Éveil Musical": "Découverte musicale pour les tout-petits",
        "Arts Plastiques": "Création artistique pluridisciplinaire",
        "Robotique Junior": "Construction et programmation de robots",
        "Stop Motion": "Création de films d'animation en stop motion",
        "Calligraphie": "Art de la belle écriture",
        "Atelier Philo": "Discussion philosophique pour enfants",
        "Tricot Créatif": "Réalisation d'accessoires au tricot",
        "Fresque Collective": "Réalisation d'une fresque murale collective",
        "Marionnettes": "Fabrication et manipulation de marionnettes",
        "Poterie Tour": "Tournage de pièces en céramique",
        "Anglais Ludique": "Apprentissage de l'anglais par le jeu",
        "Atelier Nature": "Découverte de la nature et de l'environnement",
        "Tissage Brésilien": "Création de bracelets brésiliens",
        "Mosaïque": "Art de la mosaïque",
        "Création Bijoux": "Fabrication de bijoux fantaisie",
        "Atelier Chant": "Techniques vocales et chants collectifs",
        "Percussions Africaines": "Rythmes et percussions d'Afrique",
        "Théâtre Ombres": "Théâtre d'ombres chinoises",
        "Linogravure": "Technique de gravure sur linoléum",
        "Aquarelle": "Initiation à l'aquarelle",
        "Atelier Cartes": "Création de cartes artisanales",
        "Compostage": "Apprendre à composter ses déchets",
        "Reliure Carnet": "Reliure artisanale de carnets",
        "Jeux de Société Géants": "Jeux de société en format XXL",
        "Atelier Récup": "Création à partir d'objets recyclés",
        "Vannerie": "Tressage de paniers en osier",
        "Création Papier": "Créations en papier mâché",
        "Manga Débutant": "Dessin manga pour débutants",
        "Atelier Masques": "Fabrication de masques vénitiens",
        "Tapis Lecture": "Lecture d'histoires sur un tapis magique",
        "Karaoké": "Soirée karaoké conviviale",
        "Atelier Bulles": "Création de bulles de savon géantes",
        "Herbier Créatif": "Création d'un herbier artistique",
        "Bricolage Nature": "Bricolage avec des éléments naturels",
        "Atelier Sable": "Peinture et création avec du sable",
        "Création Mobile": "Fabrication de mobiles décoratifs",
        "Pâte Fimo": "Modelage de pâte polymère",
        "Land Art": "Créations artistiques en pleine nature",
        "Atelier Laine": "Créations en laine feutrée",
        "Perles à Repasser": "Création de motifs avec perles à repasser",
        "Tampons Créatifs": "Gravure et impression de tampons",
        "Vitrail Débutant": "Initiation à l'art du vitrail",
        "Atelier Céramique": "Techniques de céramique avancées",
        "Cadres Nature": "Fabrication de cadres en éléments naturels",
        "Atelier Floral": "Compositions florales créatives",
        "Bougies Déco": "Fabrication de bougies décoratives",
        "Bijoux Résine": "Création de bijoux en résine",
        "Atelier Raku": "Technique de cuisson Raku",
        "Furoshiki": "Art japonais du pliage de tissu",
        "Teinture Végétale": "Teinture naturelle avec des plantes",
        "Kintsugi": "Art japonais de réparation par l'or",
        "Atelier Encre": "Techniques d'encres et lavis",
        "Sérigraphie": "Impression sérigraphique artisanale",
        "Diorama": "Création de scènes miniatures",
        "Cyanotype": "Photographie bleu de Prusse",
    }
    return descs.get(title, "Atelier créatif et ludique")


class Command(BaseCommand):
    help = "Génère 69 ateliers de démonstration avec participants"

    def handle(self, *args, **options):
        self.stdout.write("Génération des données de démonstration...")
        self.verify_prerequisites()
        self.clean_existing()
        anor = User.objects.get(username="anor")
        locations = list(VisitorLocation.objects.filter(is_active=True))
        today = timezone.now().date()
        current_year = today.year
        random.seed(42)

        workshop_data = []
        idx = 0

        months_schedule = [
            ("Février", date(current_year, 2, 1), 12),
            ("Mars", date(current_year, 3, 1), 14),
            ("Avril", date(current_year, 4, 1), 14),
            ("Mai", date(current_year, 5, 1), 14),
            ("Juin", date(current_year, 6, 1), 8),
            ("Juillet", date(current_year, 7, 1), 7),
        ]

        for month_name, month_start, count in months_schedule:
            self.stdout.write(f"  {month_name} : {count} ateliers")
            days_in_month = (
                (
                    date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)
                ).day
                if month_start.month < 12
                else 31
            )

            for i in range(count):
                day_offset = i * (days_in_month // count)
                day_offset = min(day_offset, days_in_month - 1)
                d = date(month_start.year, month_start.month, day_offset + 1)

                title = WORKSHOP_TITLES[idx % len(WORKSHOP_TITLES)]
                idx += 1

                loc = random.choice(locations)
                is_multi = random.random() < 0.2
                ed = d + timedelta(days=random.randint(1, 3)) if is_multi else None

                hour = random.randint(9, 17)
                duration = random.choice([1, 1, 1, 2, 2, 3])
                st = time(hour, 0)
                et = time(hour + duration, 0)

                age_profile = random.choice(AGE_RANGES)
                is_all_ages, min_age, max_age = (
                    age_profile[2],
                    age_profile[0],
                    age_profile[1],
                )

                capacity = random.choice([8, 10, 12, 15, 15, 15, 20, 25, 30])

                is_newsletter = True if d.month == 7 else random.random() < 0.7
                is_class = random.random() < 0.08
                remind = random.random() < 0.5 and d < today

                workshop_data.append(
                    {
                        "title": title,
                        "start_date": d,
                        "end_date": ed,
                        "start_time": st,
                        "end_time": et,
                        "location": loc,
                        "max_participants": capacity,
                        "is_all_ages": is_all_ages,
                        "min_age": min_age,
                        "max_age": max_age,
                        "newsletter": is_newsletter,
                        "is_class_welcome": is_class,
                        "reminder_sent": remind,
                    }
                )

        for ws in workshop_data:
            ws_obj = create_workshop(**ws)

            if ws["start_date"] >= today:
                is_future = True
            elif ws["start_date"] < today - timedelta(days=60):
                is_future = False
            else:
                is_future = False

            if ws["start_date"] >= today:
                max_part = 0
            elif ws["start_date"].month == 2:
                if ws["start_date"].day <= 10:
                    max_part = 0
                else:
                    max_part = random.randint(1, 5)
            elif ws["start_date"].month == 6 and ws["start_date"].day > 25:
                max_part = 0
            else:
                max_part = random.randint(0, ws["max_participants"] + 3)

            if max_part > ws["max_participants"]:
                over = max_part - ws["max_participants"]
                conf = ws["max_participants"]
                wait = random.randint(0, over)
                cancel = max_part - conf - wait
                total_part = conf + wait + cancel
                n_conf = min(total_part, conf)
                n_wait = min(wait, total_part - n_conf)
                n_cancel = total_part - n_conf - n_wait
            elif max_part == ws["max_participants"]:
                n_conf = max_part
                n_wait = random.randint(0, 3)
                n_cancel = random.randint(0, 2)
            else:
                n_conf = max_part
                n_wait = random.randint(0, 2) if random.random() < 0.3 else 0
                n_cancel = random.randint(0, 1) if random.random() < 0.2 else 0
                total_space = ws["max_participants"] - n_conf
                n_wait = min(n_wait, total_space)
                n_cancel = min(n_cancel, ws["max_participants"] - n_conf - n_wait)

            for _ in range(n_conf):
                WorkshopParticipant.objects.create(
                    workshop=ws_obj,
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    age=random.randint(5, 75),
                    status="confirmed",
                    added_by=anor,
                )
            for _ in range(n_wait):
                WorkshopParticipant.objects.create(
                    workshop=ws_obj,
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    age=random.randint(5, 75),
                    status="waiting",
                    added_by=anor,
                )
            for _ in range(n_cancel):
                WorkshopParticipant.objects.create(
                    workshop=ws_obj,
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    age=random.randint(5, 75),
                    status="cancelled",
                    added_by=anor,
                )

        overview = Workshop.objects.filter(created_by=anor).count()
        participants = WorkshopParticipant.objects.filter(
            workshop__created_by=anor
        ).count()
        past_count = Workshop.objects.filter(
            created_by=anor, start_date__lt=today
        ).count()
        upcoming_count = Workshop.objects.filter(
            created_by=anor, start_date__gte=today
        ).count()
        full_count = (
            Workshop.objects.filter(created_by=anor)
            .extra(
                where=[
                    "(SELECT COUNT(*) FROM library_workshops_workshopparticipant "
                    "WHERE workshop_id = library_workshops_workshop.id "
                    "AND status = 'confirmed') >= max_participants"
                ]
            )
            .count()
        )
        newsletter_count = Workshop.objects.filter(
            created_by=anor, newsletter=True
        ).count()
        july_newsletter = Workshop.objects.filter(
            created_by=anor, start_date__month=7, newsletter=True
        ).count()
        class_welcome = Workshop.objects.filter(
            created_by=anor, is_class_welcome=True
        ).count()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f">> {overview} ateliers generes pour anor")
        )
        self.stdout.write(f"  - Passés : {past_count}")
        self.stdout.write(f"  - À venir  : {upcoming_count}")
        self.stdout.write(f"  - Complets  : {full_count}")
        self.stdout.write(f"  - Newsletter : {newsletter_count}")
        self.stdout.write(f"  - Juillet newsletter : {july_newsletter}")
        self.stdout.write(f"  - Accueil de classe : {class_welcome}")
        self.stdout.write(f"  - Participants créés : {participants}")

    def verify_prerequisites(self):
        try:
            User.objects.get(username="anor")
        except User.DoesNotExist:
            self.stderr.write(
                self.style.ERROR("L'utilisateur 'anor' n'existe pas. Créez-le d'abord.")
            )
            return
        active = VisitorLocation.objects.filter(is_active=True).count()
        if active == 0:
            self.stderr.write(
                self.style.ERROR("Aucun lieu actif. Créez des lieux d'abord.")
            )
            return
        self.stdout.write(f"  Utilisateur anor trouvé, {active} lieux actifs")

    def clean_existing(self):
        anor = User.objects.get(username="anor")
        existing = Workshop.objects.filter(created_by=anor)
        count = existing.count()
        if count > 0:
            WorkshopParticipant.objects.filter(workshop__created_by=anor).delete()
            existing.delete()
            self.stdout.write(f"  {count} ateliers existants supprimés")
