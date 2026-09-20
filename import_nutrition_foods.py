import asyncio

from nutrition.usda_importer import USDAFoodImporter


async def main():
    importer = USDAFoodImporter()

    await importer.import_all_foods()


if __name__ == "__main__":
    asyncio.run(main())