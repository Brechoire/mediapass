import random
import textwrap
from datetime import date, time, timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from library_workshops.models import Workshop
from visitor_tracking.models import Location as VisitorLocation

# 12 ateliers réalistes complets, pensés rentrée sept/oct
# Chaque entrée est un gabarit réutilisable (titre + description riche + meta)
WORKSHOP_TEMPLATES = [
    {
        "title": "Rentrée littéraire : coups de cœur des bibliothécaires",
        "description": (
            "Venez découvrir la sélection rentrée littéraire de vos bibliothécaires ! "
            "Présentation vivante de 10 romans incontournables, lectures d'extraits et échanges. "
            "Repartez avec votre liste personnalisée. Tout public, entrée libre."
        ),
        "is_all_ages": True,
        "capacity": 30,
        "duration_h": 2,
        "preferred_days": [2, 5],  # mercredi, samedi
        "start_hour": 15,
    },
    {
        "title": "Heure du conte : Forêts enchantées",
        "description": (
            "Les conteuses vous emmènent au cœur des forêts enchantées : loups, lutins et arbres qui parlent. "
            "Un moment magique pour les 3-7 ans accompagnés de leurs parents. Tapis lecture et petites surprises."
        ),
        "is_all_ages": False,
        "min_age": 3,
        "max_age": 7,
        "capacity": 20,
        "duration_h": 1,
        "preferred_days": [2, 5],
        "start_hour": 10,
    },
    {
        "title": "Atelier Fête de la Science : fusées à eau",
        "description": (
            "Dans le cadre de la Fête de la Science, construisez et lancez vos fusées à eau ! "
            "Comprendre la pression, la trajectoire et la gravité en s'amusant. Atelier en extérieur si météo clémente. "
            "De 8 à 12 ans, matériel fourni."
        ),
        "is_all_ages": False,
        "min_age": 8,
        "max_age": 12,
        "capacity": 15,
        "duration_h": 2,
        "preferred_days": [2, 5, 6],
        "start_hour": 14,
    },
    {
        "title": "Club Manga : dessine ton héros",
        "description": (
            "Tu aimes Naruto, One Piece ou Spy x Family ? Apprends les bases du dessin manga : visages, expressions, "
            "trames et mise en page. Apporte tes feutres si tu en as. Ados 11-16 ans, débutants bienvenus."
        ),
        "is_all_ages": False,
        "min_age": 11,
        "max_age": 16,
        "capacity": 12,
        "duration_h": 2,
        "preferred_days": [2, 3],
        "start_hour": 14,
    },
    {
        "title": "Atelier numérique : s'initier à Canva",
        "description": (
            "Créez vos affiches, invitations et posts Instagram avec Canva. Prise en main pas à pas, astuces de mise en page "
            "et export PDF. Apportez votre ordinateur portable si possible. Adultes, débutants acceptés."
        ),
        "is_all_ages": False,
        "min_age": 16,
        "max_age": None,
        "capacity": 10,
        "duration_h": 2,
        "preferred_days": [1, 3, 5],
        "start_hour": 10,
    },
    {
        "title": "Bébés lecteurs : comptines d'automne",
        "description": (
            "Un cocon doux pour les tout-petits (0-3 ans) : comptines, jeux de doigts et livres tissus autour de l'automne. "
            "Pommes, feuilles et doudous au programme. Avec les parents ou assistantes maternelles."
        ),
        "is_all_ages": False,
        "min_age": 0,
        "max_age": 3,
        "capacity": 12,
        "duration_h": 1,
        "preferred_days": [1, 2],
        "start_hour": 10,
    },
    {
        "title": "Café philo : faut-il déconnecter ?",
        "description": (
            "Le café philo fait sa rentrée : faut-il déconnecter pour mieux vivre ? Discussion ouverte animée par un médiateur, "
            "sans jargon, dans une ambiance bienveillante. Adultes et ados dès 15 ans."
        ),
        "is_all_ages": False,
        "min_age": 15,
        "max_age": None,
        "capacity": 25,
        "duration_h": 2,
        "preferred_days": [4, 5],
        "start_hour": 18,
    },
    {
        "title": "Atelier Cyanotype : bleu d'automne",
        "description": (
            "Initiez-vous au cyanotype, procédé photographique bleu de Prusse. Apportez feuilles, dentelles ou négatifs, "
            "repartez avec vos tirages. Atelier créatif adultes/ados dès 12 ans, tout le matériel est fourni."
        ),
        "is_all_ages": False,
        "min_age": 12,
        "max_age": None,
        "capacity": 10,
        "duration_h": 2,
        "preferred_days": [5, 6],
        "start_hour": 14,
    },
    {
        "title": "Soirée jeux de société géants",
        "description": (
            "En famille ou entre amis, redécouvrez les classiques en XXL et testez les nouveautés de la ludothèque. "
            "Ambiance conviviale, boissons chaudes offertes. Tout public, sans inscription obligatoire mais conseillée."
        ),
        "is_all_ages": True,
        "capacity": 40,
        "duration_h": 3,
        "preferred_days": [4, 5],
        "start_hour": 18,
    },
    {
        "title": "Atelier d'écriture : lettres d'automne",
        "description": (
            "Et si vous écriviez la lettre que vous n'avez jamais osé envoyer ? Jeux d'écriture, contraintes ludiques et "
            "partages bienveillants. Animé par une auteure locale. Adultes, tous niveaux."
        ),
        "is_all_ages": False,
        "min_age": 16,
        "max_age": None,
        "capacity": 12,
        "duration_h": 2,
        "preferred_days": [2, 5],
        "start_hour": 14,
    },
    {
        "title": "Éveil musical : petites percussions",
        "description": (
            "Tap, tape, secoue ! Les 3-6 ans explorent les rythmes avec petites percussions, xylophones et chansons. "
            "Un atelier joyeux animé par une musicienne intervenante. Parents bienvenus."
        ),
        "is_all_ages": False,
        "min_age": 3,
        "max_age": 6,
        "capacity": 14,
        "duration_h": 1,
        "preferred_days": [2, 3],
        "start_hour": 10,
    },
    {
        "title": "Repair Café & atelier récup",
        "description": (
            "Donnez une seconde vie à vos objets : réparation, customisation et création à partir de matériaux de récup. "
            "Bénévoles bricoleurs présents pour vous guider. Tout public, apportez un objet à réparer si vous le souhaitez."
        ),
        "is_all_ages": True,
        "capacity": 20,
        "duration_h": 3,
        "preferred_days": [5],
        "start_hour": 14,
    },
]

POSTER_PALETTE = [
    ("#4a6fa5", "#e8eef7"),
    ("#b54a5a", "#fbe8eb"),
    ("#3da58a", "#e6f5ef"),
    ("#b8860b", "#fff4dd"),
    ("#7a5ea5", "#ece6f5"),
    ("#2f7a6a", "#dff0eb"),
]


def _fake_poster(title: str, subtitle: str = "Médi@'pass") -> ContentFile:
    """Génère une fausse affiche 600x800 via Pillow (fond uni + titre)."""
    bg, fg = random.choice(POSTER_PALETTE)
    img = Image.new("RGB", (600, 800), bg)
    draw = ImageDraw.Draw(img)
    # diagonale subtile
    draw.polygon([(0, 600), (600, 400), (600, 800), (0, 800)], fill="#00000018")
    # cadre
    draw.rounded_rectangle([18, 18, 582, 782], radius=18, outline="#ffffff55", width=3)

    # titre enrobé
    # tente une police truetype si disponible, sinon défaut
    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_sub = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # découpage manuel du titre en 3-4 lignes
    lines = textwrap.wrap(title, width=22)
    y = 220
    for line in lines[:4]:
        # centré
        bbox = draw.textbbox((0, 0), line, font=font_title)
        w = bbox[2] - bbox[0]
        draw.text(((600 - w) / 2, y), line, font=font_title, fill="white")
        y += 46
    # sous-titre
    bbox = draw.textbbox((0, 0), subtitle, font=font_sub)
    w = bbox[2] - bbox[0]
    draw.text(((600 - w) / 2, 620), subtitle, font=font_sub, fill="#ffffffcc")
    # mois
    draw.text((24, 752), "Sept-Oct 2026", font=font_sub, fill="#ffffff99")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ContentFile(buf.getvalue(), name="poster.png")


def _pick_dates_for_month(year: int, month: int, count: int):
    """Répartit `count` dates sur le mois en visant mercredis/samedis 1x/sem."""
    # génère tous les mercredis et samedis du mois, puis complète aléatoirement
    candidates = []
    # 0=lundi ... 6=dimanche ; mercredi=2, samedi=5
    for day in range(1, 32):
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        if d.weekday() in (2, 5):
            candidates.append(d)
    # mélange et complète si besoin
    random.shuffle(candidates)
    # si pas assez de mercredis/samedis, complète avec jours ouvrables aléatoires
    all_days = [
        date(year, month, d) for d in range(1, 32) if _valid_date(year, month, d)
    ]
    random.shuffle(all_days)
    picked = []
    for d in candidates:
        if len(picked) >= count:
            break
        picked.append(d)
    for d in all_days:
        if len(picked) >= count:
            break
        if d not in picked:
            picked.append(d)
    picked = sorted(picked)[:count]
    return picked


def _valid_date(year, month, day):
    try:
        date(year, month, day)
        return True
    except ValueError:
        return False


class Command(BaseCommand):
    help = "Génère 6 ateliers newsletter réalistes par médiathèque pour septembre et octobre (ajout)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-mediatheque",
            type=int,
            default=6,
            help="Nombre d'ateliers à ajouter par médiathèque (répartis sept+oct, défaut 6).",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Année cible (défaut: année en cours).",
        )
        parser.add_argument(
            "--users",
            nargs="*",
            default=None,
            help="Usernames des médiathèques ciblées (défaut: tous les membres du groupe mediatheque).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui serait créé sans rien écrire.",
        )

    def handle(self, *args, **options):
        per = options["per_mediatheque"]
        year = options["year"] or timezone.now().date().year
        dry_run = options["dry_run"]
        usernames = options["users"]

        # 2 médiathèques attendues : on cible par défaut les membres du groupe mediatheque
        # en excluant les comptes de test si besoin, mais on respecte --users si fourni
        if usernames:
            med_users = list(User.objects.filter(username__in=usernames))
            missing = set(usernames) - {u.username for u in med_users}
            if missing:
                self.stderr.write(
                    self.style.WARNING(
                        f"Utilisateurs introuvables ignorés: {', '.join(missing)}"
                    )
                )
        else:
            med_users = list(
                User.objects.filter(groups__name="mediatheque").order_by("username")
            )
            # si 0, fallback sur anor/trelon
            if not med_users:
                med_users = list(User.objects.filter(username__in=["anor", "trelon"]))

        if not med_users:
            self.stderr.write(
                self.style.ERROR("Aucune médiathèque trouvée (groupe mediatheque).")
            )
            return

        # si l'utilisateur a dit "2 médiathèques" et qu'on en a 4, on en prend 2 par défaut
        # on privilégie les comptes les plus réalistes (anor + trelon ou wignehies)
        # mais on respecte le choix explicite --users ; sinon on garde tous pour maximiser
        # Ici on garde tous, l'énoncé dit "2 dans la bdd" -> on limite à 2 si >2 et pas de filtre
        if usernames is None and len(med_users) > 2:
            # priorité : anor, trelon, wignehies dans cet ordre
            preferred = ["anor", "trelon", "wignehies", "testmediatheque"]
            ordered = sorted(
                med_users,
                key=lambda u: (
                    preferred.index(u.username) if u.username in preferred else 99
                ),
            )
            med_users = ordered[:2]
            self.stdout.write(
                self.style.WARNING(
                    f"Plus de 2 médiathèques trouvées, ciblage des 2 principales: {', '.join(u.username for u in med_users)}"
                )
            )

        total_to_create = per * len(med_users)
        self.stdout.write(
            f"Année cible : {year} | {per} ateliers/médiathèque sur sept.+oct. => {total_to_create} ateliers au total"
        )
        for u in med_users:
            locs = list(VisitorLocation.objects.filter(user=u, is_active=True))
            if not locs:
                # fallback lieux globaux actifs
                locs = list(VisitorLocation.objects.filter(is_active=True)[:3])
            self.stdout.write(f"  - {u.username}: {len(locs)} lieu(x) actif(s)")

        # répartition sept/oct : moitié chacun (ex. 6 => 3+3)
        sept_n = per // 2
        oct_n = per - sept_n
        sept_dates_pool = _pick_dates_for_month(
            year, 9, max(sept_n * len(med_users), len(WORKSHOP_TEMPLATES))
        )
        oct_dates_pool = _pick_dates_for_month(
            year, 10, max(oct_n * len(med_users), len(WORKSHOP_TEMPLATES))
        )
        # on va piocher dedans séquentiellement pour éviter même jour pour toutes les médiathèques
        random.seed(year * 100 + per)

        created = []
        tmpl_idx = 0
        for med_user in med_users:
            locs = list(VisitorLocation.objects.filter(user=med_user, is_active=True))
            if not locs:
                locs = list(VisitorLocation.objects.filter(is_active=True)[:3])
            # mélange des templates pour varier par médiathèque
            templates = WORKSHOP_TEMPLATES[:]
            random.shuffle(templates)

            # septembre
            for i in range(sept_n):
                tmpl = templates[tmpl_idx % len(templates)]
                tmpl_idx += 1
                d = (
                    sept_dates_pool.pop(0)
                    if sept_dates_pool
                    else date(year, 9, 10 + i * 3)
                )
                created.append(self._create_one(med_user, locs, d, tmpl, dry_run))
            # octobre
            for i in range(oct_n):
                tmpl = templates[tmpl_idx % len(templates)]
                tmpl_idx += 1
                d = (
                    oct_dates_pool.pop(0)
                    if oct_dates_pool
                    else date(year, 10, 5 + i * 3)
                )
                created.append(self._create_one(med_user, locs, d, tmpl, dry_run))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] {len(created)} ateliers auraient été créés."
                )
            )
            return

        ok = len([c for c in created if c])
        self.stdout.write(
            self.style.SUCCESS(f"{ok} ateliers newsletter créés ({per}/médiathèque).")
        )
        # résumé par médiathèque
        for med_user in med_users:
            count = Workshop.objects.filter(
                created_by=med_user,
                newsletter=True,
                start_date__year=year,
                start_date__month__in=[9, 10],
            ).count()
            self.stdout.write(
                f"  - {med_user.username}: {count} ateliers newsletter en sept-oct {year}"
            )

    def _create_one(self, user, locations, d: date, tmpl: dict, dry_run: bool):
        loc = random.choice(locations) if locations else None
        st = time(tmpl["start_hour"], 0)
        et = time(min(tmpl["start_hour"] + tmpl["duration_h"], 20), 0)
        title = tmpl["title"]
        desc = tmpl["description"]
        # petite variation de titre pour éviter doublons exacts si même template revient
        # (on garde le titre brut pour la newsletter, la dédup est gérée)
        kwargs = dict(
            title=title,
            description=desc,
            start_date=d,
            end_date=None,
            start_time=st,
            end_time=et,
            location=loc,
            max_participants=tmpl["capacity"],
            is_all_ages=tmpl["is_all_ages"],
            min_age=tmpl.get("min_age"),
            max_age=tmpl.get("max_age"),
            newsletter=True,
            is_class_welcome=False,
            reminder_sent=False,
            created_by=user,
            status="active",
        )
        if dry_run:
            self.stdout.write(
                f"    [dry-run] {user.username} | {d} {st.strftime('%Hh')} | {title} @ {loc.name if loc else '—'}"
            )
            return None

        ws = Workshop.objects.create(**kwargs)
        # faux visuel
        try:
            poster_file = _fake_poster(
                title, subtitle=loc.name if loc else "Médiathèque"
            )
            ws.poster.save(f"newsletter_{ws.pk}.png", poster_file, save=True)
        except Exception as exc:
            self.stderr.write(
                self.style.WARNING(f"  Poster échoué pour {title}: {exc}")
            )

        self.stdout.write(f"    {user.username} | {d} {st.strftime('%Hh')} | {title}")
        return ws
