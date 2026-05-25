import os
from hms import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_ENV') != 'production', host='0.0.0.0', port=5000)
