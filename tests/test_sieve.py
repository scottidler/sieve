from sieve.sieve import Sieve, Filter, Spec

def test_sieve():
    sieve = Sieve(creds_json='./.creds.json', sieve_yml='./sieve.yml')
    assert sieve, 'sieve is not None'

# test instantiation of a filter
def test_filter():
    filter = Filter()
    assert filter != None, 'filter is not None'



# test instantiation of a spec
def test_spec():
    sieve = Sieve(creds_json='./.creds.json', sieve_yml='./sieve.yml')
    spec = Spec(sieve)
    assert spec != None, 'spec is not None'

#build a filter
def test_build_filter():
    name = 'test'
    actions = ['archive']
    headers = {
        'from': 'tyler@tatari.tv',
    }
    filter = Filter(name=name, actions=actions, headers=headers)
    assert filter != None, 'filter is not None'

# compare different filters
def test_compare_filters():
    filter1 = Filter(name='test', actions=['archive'], headers={'from': 'tyler@tatari.tv'})
    filter2 = Filter(name='test', actions=['archive'], headers={'from': 'scott.idler@tatari.tv'})
    assert filter1 != filter2, 'filters are not equal'

# compare identical filters
def test_compare_filters():
    filter1 = Filter(name='test', actions=['archive'], headers={'from': 'tt'})
    filter2 = Filter(name='test', actions=['archive'], headers={'from': 'tt'})
    assert filter1 == filter2, 'filters are equal'

# test to_json on Filter
def test_to_json():
    filter = Filter(name='test', actions=['archive'], headers={'from': 'tt'})
    filter_json = filter.to_json()
    assert filter_json != None, 'filter_json is not None'

# test to_json on Filter against expected json
def test_to_json2():
    headers = {
        'from': 'tt',
    }
    filter = Filter(name='test', actions=['archive'], **headers)
    actual = filter.to_json()
    expected = {
        'name': 'test',
        'actions': ('archive',),
        'headers': {'from': ('tt',)},
    }
    assert actual == expected, 'filter_json is equal to expected_json'