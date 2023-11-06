import os
from dataextractai.parsers.wellsfargo_bank_parser import (
    run as run_wells_fargo_bank_parser,
)
from dataextractai.parsers.wellsfargo_mastercard_parser import (
    run as run_wells_fargo_mastercard_parser,
)
from dataextractai.parsers.amazon_parser import run as run_amazon_parser
from dataextractai.parsers.bofa_bank_parser import run as run_bofa_bank_parser
from dataextractai.parsers.bofa_visa_parser import run as run_bofa_visa_parser
from dataextractai.parsers.chase_visa_parser import run as run_chase_visa_parser


def run_all_parsers():
    print("Running all parsers...")

    # Run Amazon parser
    print("\nRunning Amazon parser...")
    run_amazon_parser()

    # Run Bank of America bank parser
    print("\nRunning Bank of America bank parser...")
    run_bofa_bank_parser()

    # Run Bank of America VISA parser
    print("\nRunning Bank of America VISA parser...")
    run_bofa_visa_parser()

    # Run Chase VISA parser
    print("\nRunning Chase VISA parser...")
    run_chase_visa_parser()

    # Run Wells Fargo bank parser
    print("\nRunning Wells Fargo bank parser...")
    run_wells_fargo_bank_parser()

    # Run Wells Fargo MasterCard parser
    print("\nRunning Wells Fargo MasterCard parser...")
    run_wells_fargo_mastercard_parser()

    print("\nAll parsers have been executed.")


if __name__ == "__main__":
    run_all_parsers()
