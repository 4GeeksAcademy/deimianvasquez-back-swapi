"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
from flask import Flask, request, jsonify, url_for
from flask_migrate import Migrate
from flask_swagger import swagger
from flask_cors import CORS
from utils import APIException, generate_sitemap
from admin import setup_admin
from models import db, User, People
# from models import Person
import requests
from requests.exceptions import RequestException

app = Flask(__name__)
app.url_map.strict_slashes = False

db_url = os.getenv("DATABASE_URL")
if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace(
        "postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

MIGRATE = Migrate(app, db)
db.init_app(app)
CORS(app)
setup_admin(app)

# Handle/serialize errors like a JSON object


@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# generate sitemap with all your endpoints


@app.route('/')
def sitemap():
    return generate_sitemap(app)


@app.route('/user', methods=['GET'])
def handle_hello():

    response_body = {
        "msg": "Hello, this is your GET /user response "
    }

    return jsonify(response_body), 200


@app.route("/people/population", methods=["POST"])
def people_population():
    """
        Aquí populams la bade dedatos se people
    """

    url_people = "https://www.swapi.tech/api/people?page=1&limit=83"
    summary = {
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "failed": 0
    }

    try:
        response = requests.get(url_people, timeout=15)
        data = response.json()
    except RequestException as err:
        return jsonify({"message": f"Error al traer los personajes: {err.args}"})

    for person in data.get("results", []):
        try:
            person_details_response = requests.get(
                person.get("url"), timeout=15)
            person_details = person_details_response.json()

            properties = person_details["result"]["properties"]
            name = properties.get("name")

            if not name:
                summary["failed"] += 1
                continue

            existing_person = People.query.filter_by(name=name).first()

            if existing_person:
                existing_person.height = properties.get("height")
                existing_person.mass = properties.get("mass")
                existing_person.birth_year = properties.get("birth_year")
                existing_person.gender = properties.get("gender")
                summary["updated"] += 1

            else:
                new_people = People(
                    name=name,
                    mass=properties.get("mass"),
                    birth_year=properties.get("birth_year"),
                    gender=properties.get("gender"),
                    height=properties.get("height")
                )
                db.session.add(new_people)
                summary["inserted"] += 1
            summary["processed"] += 1
        except Exception as err:
            summary["failed"] += 1

    try:
        db.session.commit()
    except Exception as err:
        db.session.rollback()
        return jsonify({"message": f"Error en la base de datos: {err.args}"})

    return jsonify({
        "message": "Populación finalizada con exito",
        "summary": summary
    }), 200


# this only runs if `$ python src/app.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
