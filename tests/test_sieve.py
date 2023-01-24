from sieve.sieve import Sieve

def test_sieve():
    sieve = Sieve(creds_json='./.creds.json', sieve_yml='./sieve.yml')
    assert sieve, 'sieve is not None'