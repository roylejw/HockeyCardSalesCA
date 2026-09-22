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
            "2023-24 Upper Deck Boston Bruins Centennial Hockey Hobby Tin",
            "2025-26 Upper Deck Series 1 Hockey Fat Pack",
            "Upper Deck: 2025-26 MVP Hockey - Hobby Booster Pack",
            "2025-26 Upper Deck MVP Hockey Hobby Pack",
            "2025-26 Topps Chrome Basketball Hobby Box",
        ]:
            self.assertIsNone(classify(title), title)


if __name__ == "__main__":
    unittest.main()
