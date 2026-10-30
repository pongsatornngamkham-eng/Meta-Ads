import importlib.util
from pathlib import Path
import pytest
from dotenv import dotenv_values
from app.passwords import password_hash

spec=importlib.util.spec_from_file_location('setup_dashboard',Path(__file__).parents[2]/'setup_dashboard.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


def test_setup_preserves_other_secrets_and_replaces_duplicates_atomically(tmp_path):
    env=tmp_path/'.env'
    env.write_text('\ufeffMETA_ACCESS_TOKEN=existing-secret\nDASHBOARD_OWNER=old\nexport DASHBOARD_OWNER=duplicate\n# keep comment\n',encoding='utf-8')
    setup.save_values(env,{'DASHBOARD_OWNER':'new-owner','MAKE_INGEST_TOKEN':'new-local-test-key'})
    text=env.read_text()
    assert 'META_ACCESS_TOKEN=existing-secret' in text and '# keep comment' in text
    assert text.count('DASHBOARD_OWNER=')==1 and 'DASHBOARD_OWNER=new-owner' in text
    assert list(tmp_path.glob('.env.dashboard-*'))==[]


def test_setup_refuses_linked_secret_file(tmp_path):
    original=tmp_path/'original';original.write_text('unchanged')
    env=tmp_path/'.env';env.symlink_to(original)
    with pytest.raises(ValueError):setup.save_values(env,{'DASHBOARD_OWNER':'owner'})
    assert original.read_text()=='unchanged'


def test_scrypt_hash_preserved_as_literal_dotenv_value(tmp_path):
    encoded=password_hash('Local test password only')
    env=tmp_path/'.env'
    setup.save_values(env,{'DASHBOARD_PASSWORD_HASH':encoded})
    assert env.read_text().startswith("DASHBOARD_PASSWORD_HASH='scrypt$")
    assert dotenv_values(env)['DASHBOARD_PASSWORD_HASH']==encoded
