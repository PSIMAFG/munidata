"""Script para probar el scraper HTTP contra un municipio específico.

Uso:
    python -m scripts.test_scraper --code 280 --year 2025 --month 1
    python -m scripts.test_scraper --code 280 --year 2025 --month 1 --type honorarios
    python -m scripts.test_scraper --code 280 --year 2025 --month 1 --type all --verbose

Debe ejecutarse desde el directorio backend/:
    cd backend && python -m scripts.test_scraper --code 280
"""
import argparse
import json
import logging
import sys
import time

from app.scraper.http_scraper import HTTPScraper


def main():
    parser = argparse.ArgumentParser(
        description="Probar el scraper HTTP de Portal Transparencia"
    )
    parser.add_argument(
        "--code", required=True,
        help="Código municipal numérico (ej: 280 para San Antonio)"
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument(
        "--type",
        choices=["honorarios", "contrata", "planta", "escalas", "all"],
        default="all",
        help="Tipo de contrato a scrappear (default: all)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Activar logging DEBUG"
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    org_code = f"MU{int(args.code):03d}"
    print(f"\n{'='*60}")
    print(f"  Testing HTTP Scraper for {org_code}")
    print(f"  Year: {args.year}  Month: {args.month}")
    print(f"{'='*60}\n")

    scraper = HTTPScraper(org_code=org_code)
    start = time.time()
    total_records = 0

    try:
        if args.type in ("honorarios", "all"):
            print(f"\n{'─'*40}")
            print(f"  HONORARIOS {args.year}/{args.month:02d}")
            print(f"{'─'*40}")
            records = scraper.scrape_honorarios(
                area="Salud", year=args.year, month=args.month
            )
            total_records += len(records)
            print(f"  Records: {len(records)}")
            if records:
                print(f"  Sample (first record):")
                print(json.dumps(records[0], indent=4, ensure_ascii=False))

        if args.type in ("contrata", "all"):
            print(f"\n{'─'*40}")
            print(f"  CONTRATA {args.year}/{args.month:02d}")
            print(f"{'─'*40}")
            records = scraper.scrape_contrata(
                area="Salud", year=args.year, month=args.month
            )
            total_records += len(records)
            print(f"  Records: {len(records)}")
            if records:
                print(f"  Sample (first record):")
                print(json.dumps(records[0], indent=4, ensure_ascii=False))

        if args.type in ("planta", "all"):
            print(f"\n{'─'*40}")
            print(f"  PLANTA {args.year}/{args.month:02d}")
            print(f"{'─'*40}")
            records = scraper.scrape_planta(
                area="Salud", year=args.year, month=args.month
            )
            total_records += len(records)
            print(f"  Records: {len(records)}")
            if records:
                print(f"  Sample (first record):")
                print(json.dumps(records[0], indent=4, ensure_ascii=False))

        if args.type in ("escalas", "all"):
            print(f"\n{'─'*40}")
            print(f"  ESCALAS {args.year}")
            print(f"{'─'*40}")
            scraper.scrape_escalas(year=args.year)
            print("  Escalas download attempted (check raw/ directory)")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        logging.exception("Scraper test failed")
        sys.exit(1)
    finally:
        scraper.close()

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  DONE: {total_records} total records in {elapsed:.1f}s")
    print(f"  Diagnostic HTML saved to: {scraper.raw_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
