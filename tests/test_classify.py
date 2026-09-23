import unittest

from tracker.classify import classify


class ClassifyTest(unittest.TestCase):
    def key(self, title):
        r = classify(title)
        return r and r["key"]

    def test_tracked(self):
        cases = {
            "2025-26 Upper Deck Series 1 Hockey Hobby Box": "2025-26|Series 1|Hobby",
            "2025-26 UPPER DECK SERIES 1 HOCKEY BLASTER BOX": "2025-26|Series 1|Blaster",
            "2024-25 O-PEE-CHEE PLATINUM HOCKEY HOBBY BOX": "2024-25|O-Pee-Chee Platinum|Hobby",
            "2019-20 Upper Deck O-Phee-Chee Hockey Hobby Box": "2019-20|O-Pee-Chee|Hobby",
            "14-15 UPPER DECK SP AUTHENTIC HOCKEY HOBBY BOX": "2014-15|SP Authentic|Hobby",
            "2020-2021 Upper Deck SP Hockey Blaster": "2020-21|SP|Blaster",
            "2025-26 UPPER DECK FLAIR HOCKEY HOBBY BOX": "2025-26|Flair|Hobby",
            "2015-16 Upper Deck Champ's Hockey Hobby Box": "2015-16|Champs|Hobby",
            "2026-27 Upper Deck MVP Hockey Blaster Box (Pre-Order)": "2026-27|MVP|Blaster",
            "2022/23 Upper Deck O-Pee-Chee Hockey 8-Pack Blaster Box": "2022-23|O-Pee-Chee|Blaster",
            "Upper Deck 2025-26 NHL Series 2 Hockey Tin": "2025-26|Series 2|Tin",
            "2023-24 Upper Deck Boston Bruins Centennial Hockey Hobby Tin": "2023-24|Boston Bruins Centennial|Tin",
            "Upper Deck 2026 Series 2 Hockey Tin": "2025-26|Series 2|Tin",
            "Upper Deck 2025 Series 1 Hockey Hobby Box": "2025-26|Series 1|Hobby",
            "Upper Deck 2025-26 Series Two Hockey Blaster Collectible Hockey Cards": "2025-26|Series 2|Blaster",
            "2023-24 Hockey - Upper Deck Extended - Boîte - Hobby (anglais)": "2023-24|Extended Series|Hobby",
            "NHL 2025-2026 Upper Deck Artifact Hockey Blaster Trading Cards": "2025-26|Artifacts|Blaster",
        }
        for title, key in cases.items():
            self.assertEqual(self.key(title), key, title)

    def test_excluded(self):
        for title in [
            "2025-26 Upper Deck AHL Hockey Hobby Box",
            "2025-26 Upper Deck Fleer Ultra PWHL Hockey Hobby Box",
            "2026 Upper Deck Team Canada Juniors Hockey Blaster Box",
            "2024-25 Upper Deck CHL Hockey Hobby Box",
            "2025-26 UPPER DECK ICE HOCKEY 8 BOX CASE",
            "ULTRA PRO ACRYLIC UPPER DECK HOCKEY HOBBY BOX HOLDER",
            "2008-09 Upper Deck Collector's Choice Hockey Hobby Packs (lot of 12 Pack )",
            "2025-26 Upper Deck Series 1 Hockey Fat Pack",
            "Upper Deck: 2025-26 MVP Hockey - Hobby Booster Pack",
            "2025-26 Upper Deck MVP Hockey Hobby Pack",
            "2025-26 Topps Chrome Basketball Hobby Box",
            "Upper Deck 2026 PWHL Blaster Box",
            "Upper Deck 2025-2026 Series 1 Hockey Cards - Gravity Feed",
            "Upper Deck 2026 Team Canada Hockey Blaster Box",
            "2025-26 Upper Deck Series 1 Hockey Mega Box",
            "2022-23 Hockey - Upper Deck Series 2 - Paquet - Hobby",
        ]:
            self.assertIsNone(classify(title), title)

    def test_baseball_tracked(self):
        cases = {
            "2024 Topps Series 1 Baseball Hobby Box": "2024|Topps Series 1|Hobby",
            "2024 Topps Series 1 Baseball Jumbo Box": "2024|Topps Series 1|Jumbo",
            "2024 Topps Series 1 Baseball Hobby Jumbo Box": "2024|Topps Series 1|Jumbo",
            "2023 Topps Chrome Update Series Baseball Hobby Box": "2023|Topps Chrome Update|Hobby",
            "2025 Bowman Chrome Baseball Hobby Box": "2025|Bowman Chrome|Hobby",
            "2024 Bowman Draft Baseball Jumbo Box": "2024|Bowman Draft|Jumbo",
            "2024 Bowman Baseball Blaster Box": "2024|Bowman|Blaster",
            "2022 Topps Chrome Baseball Breaker's Delight Box": "2022|Topps Chrome|Breaker's Delight",
            "2026 Topps Series 1 Baseball Easter Tin": "2026|Topps Series 1|Tin",
            "2023 Topps Archives Baseball Hobby Collector's Tin (Box)": "2023|Topps Archives|Tin",
            "2021 Topps Stadium Club Chrome Baseball Hobby Box": "2021|Topps Stadium Club Chrome|Hobby",
            "2024 Topps Heritage Hobby Box": "2024|Topps Heritage|Hobby",
            "2024 Topps Holiday Baseball Mega Tin": "2024|Topps Holiday|Tin",
            "2025 Topps Chrome Update Series Baseball Mega Box": "2025|Topps Chrome Update|Mega",
            "2026 Bowman Baseball Mega Box": "2026|Bowman|Mega",
            "2026 Topps Bowman Baseball Mega Box": "2026|Bowman|Mega",
            "2024 Topps Chrome Baseball Value Box": "2024|Topps Chrome|Value",
            "2024 Topps Bowman Baseball Value Box": "2024|Bowman|Value",
            "2026 Topps Series 1 Baseball Celebration Mega Box": "2026|Topps Series 1 Celebration|Mega",
            "2026 Topps Series 2 Baseball All Star Game Mega Box": "2026|Topps Series 2 All-Star Game|Mega",
            "2021 Topps Bowman Chrome Baseball Hobby Lite Box": "2021|Bowman Chrome Lite|Hobby",
            "2021 Bowman Draft Baseball First Edition Hobby Box": "2021|Bowman Draft 1st Edition|Hobby",
            "2022 Topps Series 2/Two MLB Baseball Vending Hobby Box": "2022|Topps Series 2 Vending|Hobby",
            "2023 Topps Allen &#038; Ginter Baseball Hobby Box": "2023|Topps Allen & Ginter|Hobby",
            "2021 Topps Archive Baseball Hobby Box": "2021|Topps Archives|Hobby",
        }
        for title, key in cases.items():
            r = classify(title)
            self.assertEqual(r and (r["sport"], r["key"]), ("baseball", key), title)

    def test_baseball_excluded(self):
        for title in [
            "2019 Topps Series 1 Baseball Hobby Box",           # before 2020
            "2026 Panini Prizm Baseball Hobby Box",              # not Topps
            "2025 Topps Series 1 Baseball Hanger Box",
            "2021 Topps Update Series Baseball Jumbo Pack",
            "2023 Bowman Baseball Hobby Jumbo Pack",
            "2025 Topps Series 1 Baseball Fat Pack",
            "2025 Topps Update Baseball Retail Box",
            "2024 Topps Chrome Football Hobby Box",
            "2024 Bowman University Chrome Football Hobby Box",
            "2024 Topps Chrome Hobby Box",                       # sport unknown
            "2024 Topps Series 1 Baseball Hobby Case",
            "2026 Topps Complete Sets Baseball Hobby Box",
        ]:
            self.assertIsNone(classify(title), title)


if __name__ == "__main__":
    unittest.main()
