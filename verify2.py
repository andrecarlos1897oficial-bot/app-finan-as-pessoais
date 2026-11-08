import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()
client = app.test_client()

# Make a request and check all headers
with client:
    res = client.get('/')
    print('All Set-Cookie headers:')
    for header, value in res.headers.items():
        if 'set-cookie' in header.lower() or 'set-cookie' in header.lower():
            print(f'  {header}: {value}')
    
    # Also check session transaction
    with client.session_transaction() as sessao:
        print('\nSession keys:', list(sessao.keys()))
        csrf = sessao.get('csrf_token', '')
        print('CSRF token:', csrf[:20] + '...' if len(csrf) > 20 else csrf)
    
    # Try a POST to see how cookie is set
    res2 = client.post('/perfil', data={
        'csrf_token': res.headers.get('Set-Cookie', '').split(';')[0] if 'Set-Cookie' in str(res.headers) else 'test',
        'nome': 'Teste',
        'email': 'teste@teste.com'
    }, follow_redirects=False)
    print('\nAfter POST Set-Cookie:')
    for header, value in res2.headers.items():
        if 'set-cookie' in header.lower():
            print(f'  {header}: {value}')