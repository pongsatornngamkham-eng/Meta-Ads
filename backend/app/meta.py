"""Deliberately disabled adapter boundary, not a claim of a working API integration.

The CSV-only release has no Graph API request implementation, even if an
operator sets META_CONNECTOR_ENABLED. There are no campaign mutation methods.
"""
class MetaConnectorDisabled(RuntimeError): pass

def fetch_insights(*args, **kwargs):
    raise MetaConnectorDisabled('Meta API is disabled in the CSV-only release. Complete policy review, ads_read approval and account authorization before implementing/enabling this adapter.')

def status():
    return {'enabled': False, 'mode': 'csv-only', 'version_candidate': 'v26.0',
            'required_permission': 'ads_read', 'reason': 'Permission, account access and policy/legal review are not verified'}
