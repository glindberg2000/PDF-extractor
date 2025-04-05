"""Excel formatter for creating rich transaction reports with validation and charts."""

import pandas as pd
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import PieChart, Reference
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
import json
import os


class ExcelReportFormatter:
    """Creates rich Excel reports with validation, charts, and summaries."""

    def __init__(self):
        """Initialize the Excel formatter with styles."""
        self.header_fill = PatternFill(
            start_color="1F4E78", end_color="1F4E78", fill_type="solid"
        )
        self.header_font = Font(color="FFFFFF", bold=True)
        self.header_alignment = Alignment(horizontal="center", vertical="center")

        # Define columns to show/hide
        self.visible_columns = [
            # Transaction Info
            "transaction_date",
            "description",
            "normalized_amount",
            # Payee Info (Pass 1)
            "payee",
            "payee_confidence",
            "business_description",
            "general_category",
            # Business Info (Pass 2)
            "expense_type",
            "business_percentage",
            "business_context",
            # Tax Info (Pass 3)
            "tax_category",
            "tax_subcategory",
            "worksheet",
            "tax_worksheet_line_number",
            "tax_year",
            # Review Info
            "is_reviewed",
            "review_notes",
            "last_reviewed_at",
        ]

    def _get_business_categories(self, client_name):
        """Get categories from business profile."""
        profile_path = os.path.join(
            "data", "clients", client_name, "business_profile.json"
        )
        try:
            with open(profile_path, "r") as f:
                profile = json.load(f)

            # Combine AI-generated and custom categories
            categories = set()

            # Add main categories from hierarchy
            if "category_hierarchy" in profile:
                categories.update(profile["category_hierarchy"]["main_categories"])
                # Add subcategories
                for subcats in profile["category_hierarchy"]["subcategories"].values():
                    categories.update(subcats)

            # Add custom categories
            if "custom_categories" in profile:
                categories.update(profile["custom_categories"])

            # Add AI-generated categories
            if "ai_generated_categories" in profile:
                categories.update(profile["ai_generated_categories"])

            # Add "Other" category
            categories.add("Other")

            return sorted(list(categories))
        except Exception as e:
            print(f"Error reading business profile: {e}")
            return [
                "Income",
                "Business Expense",
                "Personal Expense",
                "Transfer",
                "Other",
            ]

    def create_report(self, data: pd.DataFrame, output_path: str, client_name: str):
        """Create Excel report with validation and charts."""
        # Get categories from business profile
        categories = self._get_business_categories(client_name)
        classifications = [
            "Personal",
            "Business",
            "Mixed Use",
        ]  # Default classifications

        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Transactions"

        # Write headers
        all_columns = list(data.columns)
        for col, header in enumerate(all_columns, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.header_alignment

            # Hide columns not in visible_columns
            if header not in self.visible_columns:
                ws.column_dimensions[get_column_letter(col)].hidden = True

        # Write data
        for row in range(len(data)):
            for col, value in enumerate(data.iloc[row], 1):
                ws.cell(row=row + 2, column=col, value=value)

        # Add data validation for categories and classifications
        # Create hidden validation sheet
        validation_sheet = wb.create_sheet("_Validation")
        validation_sheet.sheet_state = "hidden"

        # Write categories and classifications
        for i, cat in enumerate(categories, 1):
            validation_sheet[f"A{i}"] = cat
        for i, cls in enumerate(classifications, 1):
            validation_sheet[f"B{i}"] = cls

        # Get column letters for validation
        try:
            category_col = get_column_letter(all_columns.index("base_category") + 1)
            class_col = get_column_letter(all_columns.index("classification") + 1)

            # Add validation to category column
            cat_validation = DataValidation(
                type="list",
                formula1=f"'_Validation'!$A$1:$A${len(categories)}",
                allow_blank=True,
            )
            ws.add_data_validation(cat_validation)
            cat_validation.add(f"{category_col}2:{category_col}{len(data)+1}")

            # Add validation to classification column
            class_validation = DataValidation(
                type="list",
                formula1=f"'_Validation'!$B$1:$B${len(classifications)}",
                allow_blank=True,
            )
            ws.add_data_validation(class_validation)
            class_validation.add(f"{class_col}2:{class_col}{len(data)+1}")
        except ValueError as e:
            print(f"Warning: Could not add validation - {e}")

        # Create summary sheet
        summary = wb.create_sheet("Summary")

        # Write summary headers
        summary_headers = [
            "Category",
            "Total Amount",
            "Transaction Count",
            "Average Amount",
        ]
        for col, header in enumerate(summary_headers, 1):
            cell = summary.cell(row=1, column=col, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.header_alignment

        # Get column letters for summary calculations
        try:
            amount_col = get_column_letter(all_columns.index("normalized_amount") + 1)
            category_col = get_column_letter(all_columns.index("base_category") + 1)
            last_row = len(data) + 1

            # Write category rows with formulas
            for row, category in enumerate(categories, 2):
                # Category name
                summary.cell(row=row, column=1, value=category)

                # Total Amount (SUMIF)
                total_formula = f'=SUMIF(Transactions!{category_col}2:{category_col}{last_row},"{category}",Transactions!{amount_col}2:{amount_col}{last_row})'
                summary.cell(row=row, column=2, value=total_formula).number_format = (
                    '"$"#,##0.00'
                )

                # Transaction Count (COUNTIF)
                count_formula = f'=COUNTIF(Transactions!{category_col}2:{category_col}{last_row},"{category}")'
                summary.cell(row=row, column=3, value=count_formula)

                # Average Amount (IF to avoid div/0)
                avg_formula = f"=IF(C{row}>0,B{row}/C{row},0)"
                summary.cell(row=row, column=4, value=avg_formula).number_format = (
                    '"$"#,##0.00'
                )

            # Add totals row
            total_row = len(categories) + 2
            summary.cell(row=total_row, column=1, value="Total").font = Font(bold=True)
            summary.cell(
                row=total_row, column=2, value=f"=SUM(B2:B{total_row-1})"
            ).number_format = '"$"#,##0.00'
            summary.cell(
                row=total_row, column=3, value=f"=SUM(C2:C{total_row-1})"
            ).font = Font(bold=True)
            summary.cell(
                row=total_row,
                column=4,
                value=f"=IF(C{total_row}>0,B{total_row}/C{total_row},0)",
            ).number_format = '"$"#,##0.00'

            # Create pie chart
            pie = PieChart()
            pie.title = "Expenses by Category"

            # Use direct references for chart data
            last_category_row = len(categories) + 1
            data_ref = Reference(
                summary, min_col=2, min_row=1, max_row=last_category_row
            )
            labels_ref = Reference(
                summary, min_col=1, min_row=2, max_row=last_category_row
            )
            pie.add_data(data_ref, titles_from_data=True)
            pie.set_categories(labels_ref)

            # Add chart to worksheet
            summary.add_chart(pie, "F2")

        except ValueError as e:
            print(f"Warning: Could not create summary calculations - {e}")

        # Auto-adjust column widths and add filters
        for sheet in [ws, summary]:
            max_col = len(all_columns) if sheet == ws else len(summary_headers)
            for col in range(1, max_col + 1):
                if not (
                    sheet == ws
                    and list(data.columns)[col - 1] not in self.visible_columns
                ):
                    sheet.column_dimensions[get_column_letter(col)].width = 15
            sheet.auto_filter.ref = f"A1:{get_column_letter(max_col)}1"

        # Create tax summary sheet if tax_category exists
        if "tax_category" in all_columns:
            try:
                tax_summary = wb.create_sheet("Tax Summary")

                # Write summary headers
                tax_headers = [
                    "Tax Category",
                    "Total Amount",
                    "Transaction Count",
                    "Average Amount",
                ]
                for col, header in enumerate(tax_headers, 1):
                    cell = tax_summary.cell(row=1, column=col, value=header)
                    cell.fill = self.header_fill
                    cell.font = self.header_font
                    cell.alignment = self.header_alignment

                # Get column letters for tax summary calculations
                amount_col = get_column_letter(
                    all_columns.index("normalized_amount") + 1
                )
                tax_col = get_column_letter(all_columns.index("tax_category") + 1)
                class_col = get_column_letter(all_columns.index("classification") + 1)
                last_row = len(data) + 1

                # Get unique tax categories
                tax_categories = set()
                for i in range(len(data)):
                    tax_cat = data.iloc[i].get("tax_category")
                    if tax_cat and str(tax_cat).lower() != "nan":
                        tax_categories.add(tax_cat)

                # Add "Other expenses" if not present
                if not tax_categories:
                    tax_categories = {"Other expenses"}

                tax_categories = sorted(list(tax_categories))

                # Write tax category rows with formulas
                for row, category in enumerate(tax_categories, 2):
                    # Category name
                    tax_summary.cell(row=row, column=1, value=category)

                    # Total Amount (SUMIFS - only business expenses with this tax category)
                    total_formula = f'=SUMIFS(Transactions!{amount_col}2:{amount_col}{last_row},Transactions!{tax_col}2:{tax_col}{last_row},"{category}",Transactions!{class_col}2:{class_col}{last_row},"Business")'
                    tax_summary.cell(
                        row=row, column=2, value=total_formula
                    ).number_format = '"$"#,##0.00'

                    # Transaction Count (COUNTIFS)
                    count_formula = f'=COUNTIFS(Transactions!{tax_col}2:{tax_col}{last_row},"{category}",Transactions!{class_col}2:{class_col}{last_row},"Business")'
                    tax_summary.cell(row=row, column=3, value=count_formula)

                    # Average Amount (IF to avoid div/0)
                    avg_formula = f"=IF(C{row}>0,B{row}/C{row},0)"
                    tax_summary.cell(
                        row=row, column=4, value=avg_formula
                    ).number_format = '"$"#,##0.00'

                # Add totals row
                total_row = len(tax_categories) + 2
                tax_summary.cell(row=total_row, column=1, value="Total").font = Font(
                    bold=True
                )
                tax_summary.cell(
                    row=total_row, column=2, value=f"=SUM(B2:B{total_row-1})"
                ).number_format = '"$"#,##0.00'
                tax_summary.cell(
                    row=total_row, column=3, value=f"=SUM(C2:C{total_row-1})"
                ).font = Font(bold=True)
                tax_summary.cell(
                    row=total_row,
                    column=4,
                    value=f"=IF(C{total_row}>0,B{total_row}/C{total_row},0)",
                ).number_format = '"$"#,##0.00'

                # Create pie chart for tax categories
                pie = PieChart()
                pie.title = "Business Expenses by Tax Category"

                # Use direct references for chart data
                last_category_row = len(tax_categories) + 1
                data_ref = Reference(
                    tax_summary, min_col=2, min_row=1, max_row=last_category_row
                )
                labels_ref = Reference(
                    tax_summary, min_col=1, min_row=2, max_row=last_category_row
                )
                pie.add_data(data_ref, titles_from_data=True)
                pie.set_categories(labels_ref)

                # Add chart to worksheet
                tax_summary.add_chart(pie, "F2")

                # Format tax summary sheet
                max_col = len(tax_headers)
                for col in range(1, max_col + 1):
                    tax_summary.column_dimensions[get_column_letter(col)].width = 15
                tax_summary.auto_filter.ref = f"A1:{get_column_letter(max_col)}1"

            except Exception as e:
                print(f"Warning: Could not create tax summary calculations - {e}")

        # Save workbook
        wb.save(output_path)
