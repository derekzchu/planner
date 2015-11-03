import gevent.pywsgi
from sqlalchemy import func
from flask import Flask, request, abort, jsonify
import json
import utils, models
from models import Status
import gevent  # Use Cooperative threading
import syslog

app = Flask(__name__)

@app.route('/inventory/<int:inv_id>')
@app.route('/inventory')
def get_inventory(inv_id = None):
    """
    Get the central inventory
    @param inv_id is the pk of the inventory item

    @return inventory
    """
    ret = []
    with utils.db_session() as session:
        if inv_id:
            query_res = session.query(models.Inventory).get(inv_id)
            if not query_res:
                raise HTTPError(404, 'Inventory not found')
            ret.append(query_res.as_dict())
        else:
            query_res = session.query(models.Inventory).all()
            for result in query_res:
                ret.append(result.as_dict())

    return json.dumps(ret)


class HTTPError(Exception):
    message = 'An error occurred'
    def __init__(self, status_code, message = None, payload = None):
        Exception.__init__(self)
        self.status_code = status_code
        if message is not None:
            self.message = message

        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

@app.errorhandler(HTTPError)
def handle_http_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def main():
    """
    Main Entry function
    """
    # Initialize the DB and delete any existing data
    models.init_db()
    utils.clear_dbs()

    utils.populate_inventory()

    # Gevent wsgi server with bottle as the wsgi app
    app.debug = True
    gevent.pywsgi.WSGIServer(('', 8088), app).serve_forever()


if __name__ == '__main__':
    main()
