"""Seed data service for initial F1 season data."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Driver, Team, Car, PowerUnit, Circuit, RaceWeekend,
    Source, Citation, EntityRelationship, StrategicAsset,
    DriverStatus, RaceStatus, AssetType, ImpactDirection, ConfidenceLabel,
    DiscoveryMethod, CircuitCategory,
)


def _now():
    return datetime.now(timezone.utc)


SEASON_2026_SCHEDULE = [
    ("Australian Grand Prix", "Melbourne", "Australia"),
    ("Chinese Grand Prix", "Shanghai", "China"),
    ("Japanese Grand Prix", "Suzuka", "Japan"),
    ("Bahrain Grand Prix", "Sakhir", "Bahrain"),
    ("Saudi Arabian Grand Prix", "Jeddah", "Saudi Arabia"),
    ("Miami Grand Prix", "Miami", "USA"),
    ("Emilia Romagna Grand Prix", "Imola", "Italy"),
    ("Monaco Grand Prix", "Monte Carlo", "Monaco"),
    ("Spanish Grand Prix", "Barcelona", "Spain"),
    ("Canadian Grand Prix", "Montreal", "Canada"),
    ("Austrian Grand Prix", "Spielberg", "Austria"),
    ("British Grand Prix", "Silverstone", "United Kingdom"),
    ("Belgian Grand Prix", "Spa-Francorchamps", "Belgium"),
    ("Hungarian Grand Prix", "Budapest", "Hungary"),
    ("Dutch Grand Prix", "Zandvoort", "Netherlands"),
    ("Italian Grand Prix", "Monza", "Italy"),
    ("Azerbaijan Grand Prix", "Baku", "Azerbaijan"),
    ("Singapore Grand Prix", "Singapore", "Singapore"),
    ("United States Grand Prix", "Austin", "USA"),
    ("Mexican Grand Prix", "Mexico City", "Mexico"),
    ("Brazilian Grand Prix", "Sao Paulo", "Brazil"),
    ("Las Vegas Grand Prix", "Las Vegas", "USA"),
    ("Qatar Grand Prix", "Lusail", "Qatar"),
    ("Abu Dhabi Grand Prix", "Yas Marina", "UAE"),
]

CIRCUIT_CHARACTERISTICS = {
    "Melbourne": ("medium", "medium", "medium", "medium", "medium"),
    "Shanghai": ("low", "medium", "high", "medium", "low"),
    "Suzuka": ("low", "high", "high", "medium", "medium"),
    "Sakhir": ("medium", "high", "medium", "very_high", "low"),
    "Jeddah": ("medium", "high", "medium", "low", "low"),
    "Miami": ("medium", "medium", "medium", "medium", "medium"),
    "Imola": ("low", "medium", "high", "medium", "medium"),
    "Monte Carlo": ("very_high", "low", "high", "low", "low"),
    "Barcelona": ("medium", "medium", "high", "medium", "low"),
    "Montreal": ("medium", "medium", "medium", "low", "medium"),
    "Spielberg": ("medium", "medium", "medium", "medium", "medium"),
    "Silverstone": ("medium", "high", "high", "medium", "high"),
    "Spa-Francorchamps": ("medium", "high", "medium", "medium", "high"),
    "Budapest": ("high", "medium", "high", "medium", "low"),
    "Zandvoort": ("medium", "medium", "high", "medium", "medium"),
    "Singapore": ("high", "medium", "high", "high", "medium"),
    "Monza": ("medium", "high", "low", "medium", "medium"),
    "Baku": ("medium", "medium", "medium", "low", "low"),
    "Austin": ("medium", "medium", "medium", "medium", "medium"),
    "Mexico City": ("medium", "medium", "medium", "low", "low"),
    "Sao Paulo": ("medium", "medium", "medium", "medium", "high"),
    "Las Vegas": ("medium", "medium", "medium", "low", "low"),
    "Lusail": ("medium", "medium", "medium", "medium", "low"),
    "Yas Marina": ("medium", "medium", "medium", "low", "low"),
}

POWER_UNITS_2026 = [
    ("Mercedes", "Mercedes-AMG High Performance Powertrains"),
    ("Ferrari", "Scuderia Ferrari"),
    ("Honda", "Honda Racing Corporation"),
    ("Red Bull Powertrains", "Red Bull Powertrains"),
    ("Audi", "Audi Sport"),
    ("Cadillac", "General Motors"),
]

TEAMS_2026 = [
    ("McLaren", "Mercedes"),
    ("Ferrari", "Ferrari"),
    ("Red Bull Racing", "Honda"),
    ("Mercedes", "Mercedes"),
    ("Aston Martin", "Honda"),
    ("Alpine", "Ferrari"),
    ("Haas", "Ferrari"),
    ("RB", "Red Bull Powertrains"),
    ("Williams", "Mercedes"),
    ("Audi", "Audi"),
    ("Cadillac", "Cadillac"),
]

DRIVERS_2026 = [
    ("Lando Norris", "McLaren", "4"),
    ("Oscar Piastri", "McLaren", "81"),
    ("Charles Leclerc", "Ferrari", "16"),
    ("Lewis Hamilton", "Ferrari", "44"),
    ("Max Verstappen", "Red Bull Racing", "1"),
    ("Liam Lawson", "Red Bull Racing", "30"),
    ("George Russell", "Mercedes", "63"),
    ("Andrea Kimi Antonelli", "Mercedes", "12"),
    ("Fernando Alonso", "Aston Martin", "14"),
    ("Lance Stroll", "Aston Martin", "18"),
    ("Pierre Gasly", "Alpine", "10"),
    ("Jack Doohan", "Alpine", "7"),
    ("Esteban Ocon", "Haas", "31"),
    ("Oliver Bearman", "Haas", "87"),
    ("Yuki Tsunoda", "RB", "22"),
    ("Isack Hadjar", "RB", "6"),
    ("Alex Albon", "Williams", "23"),
    ("Carlos Sainz", "Williams", "55"),
    ("Nico Hulkenberg", "Audi", "27"),
    ("Gabriel Bortoleto", "Audi", "5"),
    ("Patricio O'Ward", "Cadillac", "29"),
    ("Zhou Guanyu", "Cadillac", "24"),
]


def seed_database(db: Session) -> dict:
    """Seed the database with F1 2026 season data. Returns stats."""
    settings = get_settings()
    season = settings.f1_season

    stats = {"teams": 0, "drivers": 0, "power_units": 0, "cars": 0, "circuits": 0, "races": 0, "assets": 0}

    seed_source = Source(
        url=f"app://seed-data/f1-{season}",
        domain="app://seed-data",
        title=f"F1 {season} Static Season Data",
        discovery_method=DiscoveryMethod("static_dataset_import"),
        content_policy="metadata_only",
    )
    db.add(seed_source)
    db.flush()

    def _cite(entity_id_field: str, entity_id: str, claim: str, field: str):
        c = Citation(
            source_id=seed_source.id,
            url=f"app://seed-data/f1-{season}",
            title=f"F1 {season} Static Data",
            domain="app://seed-data",
            excerpt_snippet=f"Static seed data for F1 {season}",
            claim_supported=f"{claim} ({field})",
            confidence=ConfidenceLabel("high"),
        )
        setattr(c, entity_id_field, entity_id)
        db.add(c)

    pu_map: dict[str, str] = {}
    for manufacturer, full_name in POWER_UNITS_2026:
        existing = db.query(PowerUnit).filter(
            PowerUnit.manufacturer == manufacturer,
            PowerUnit.is_deleted == False,
        ).first()
        if existing:
            pu_map[manufacturer] = existing.id
            continue

        pu = PowerUnit(
            id=str(uuid.uuid4()),
            manufacturer=manufacturer,
            reliability_indicator=0.5,
            performance_indicator=0.5,
        )
        db.add(pu)
        db.flush()
        _cite("power_unit_id", pu.id, f"Power unit: {manufacturer}", "manufacturer")
        pu_map[manufacturer] = pu.id
        stats["power_units"] += 1

    team_map: dict[str, str] = {}
    car_map: dict[str, str] = {}
    for team_name, pu_manufacturer in TEAMS_2026:
        existing = db.query(Team).filter(
            Team.name == team_name,
            Team.is_deleted == False,
        ).first()
        if existing:
            team_map[team_name] = existing.id
            continue

        team = Team(name=team_name)
        db.add(team)
        db.flush()
        _cite("team_id", team.id, f"Team: {team_name}", "name")
        team_map[team_name] = team.id
        stats["teams"] += 1

        car = Car(
            chassis_name=f"{team_name} F1 {season}",
            team_id=team.id,
            power_unit_id=pu_map.get(pu_manufacturer),
            reliability_indicator=0.5,
            performance_indicator=0.5,
        )
        db.add(car)
        db.flush()
        car_map[team_name] = car.id
        stats["cars"] += 1

    for name, team_name, number in DRIVERS_2026:
        existing = db.query(Driver).filter(
            Driver.name == name,
            Driver.is_deleted == False,
        ).first()
        if existing:
            continue

        driver = Driver(
            name=name,
            team_id=team_map.get(team_name),
            driver_number=number,
            status=DriverStatus("active"),
        )
        db.add(driver)
        driver_id = driver.id
        db.flush()
        _cite("driver_id", driver.id, f"Driver: {name}", "name")
        stats["drivers"] += 1

        if team_name in team_map:
            rel = EntityRelationship(
                source_entity_type="driver",
                source_entity_id=driver.id,
                target_entity_type="team",
                target_entity_id=team_map[team_name],
                relationship_type="drives_for",
                confidence=ConfidenceLabel("high"),
            )
            db.add(rel)

    circuit_map: dict[str, str] = {}
    for gp_name, circuit, country in SEASON_2026_SCHEDULE:
        if circuit not in circuit_map:
            chars = CIRCUIT_CHARACTERISTICS.get(circuit)
            c = Circuit(
                name=circuit,
                country=country,
                overtaking_difficulty=CircuitCategory(chars[0]) if chars else None,
                power_sensitivity=CircuitCategory(chars[1]) if chars else None,
                aero_sensitivity=CircuitCategory(chars[2]) if chars else None,
                reliability_stress=CircuitCategory(chars[3]) if chars else None,
                weather_volatility=CircuitCategory(chars[4]) if chars else None,
            )
            db.add(c)
            db.flush()
            _cite("circuit_id", c.id, f"Circuit: {circuit}", "name")
            circuit_map[circuit] = c.id
            stats["circuits"] += 1

    for i, (gp_name, circuit, _) in enumerate(SEASON_2026_SCHEDULE):
        existing = db.query(RaceWeekend).filter(
            RaceWeekend.grand_prix_name == gp_name,
            RaceWeekend.season == season,
            RaceWeekend.is_deleted == False,
        ).first()
        if existing:
            continue

        race = RaceWeekend(
            grand_prix_name=gp_name,
            circuit_id=circuit_map.get(circuit),
            status=RaceStatus("scheduled"),
            has_sprint=False,
            race_order=i + 1,
            season=season,
            sessions=json.dumps([
                {"type": "practice", "label": "FP1"},
                {"type": "practice", "label": "FP2"},
                {"type": "practice", "label": "FP3"},
                {"type": "qualifying", "label": "Qualifying"},
                {"type": "race", "label": "Race"},
            ]),
        )
        db.add(race)
        db.flush()
        _cite("race_weekend_id", race.id, f"Race: {gp_name}", "grand_prix_name")
        stats["races"] += 1

        rel = EntityRelationship(
            source_entity_type="race_weekend",
            source_entity_id=race.id,
            target_entity_type="circuit",
            target_entity_id=circuit_map[circuit],
            relationship_type="held_at",
            confidence=ConfidenceLabel("high"),
        )
        db.add(rel)

    initial_assets = [
        ("2026 Car Platform", "car_development_package", None),
        ("Power Unit Reliability 2026", "reliability_upgrade", None),
    ]
    for asset_name, asset_type, team_name in initial_assets:
        existing = db.query(StrategicAsset).filter(
            StrategicAsset.name == asset_name,
            StrategicAsset.is_deleted == False,
        ).first()
        if existing:
            continue

        asset = StrategicAsset(
            name=asset_name,
            asset_type=AssetType(asset_type),
            status="active",
            directional_impact=ImpactDirection("unknown"),
            confidence=ConfidenceLabel("medium"),
        )
        db.add(asset)
        db.flush()
        _cite("strategic_asset_id", asset.id, f"Asset: {asset_name}", "name")
        stats["assets"] += 1

    db.commit()
    return stats
