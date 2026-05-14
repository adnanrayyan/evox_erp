from evox_erp.cheque_management.report_utils import run_cheque_report


def execute(filters=None):
    return run_cheque_report(filters, statuses=["Received / In Hand"])

