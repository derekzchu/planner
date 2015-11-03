import gevent.pywsgi
from sqlalchemy import func, case, literal_column
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

@app.route('/plans', methods = ['POST'])
def create_plan():
     """
     create a new plan

     @return plan dict
     """
     try:
         content = request.get_json()
         name = content['name']
     except Exception:
         raise HTTPError(400, 'Plan is missing a name')

     with utils.db_session() as session:
         new_plan = models.Plan(name)
         session.add(new_plan)

         session.flush()

         return json.dumps(new_plan.as_dict())

@app.route('/plans/<int:plan_id>')
@app.route('/plans')
def get_plans(plan_id = None):
    """
    Get all the plans.
    @param plan_id is pk of the plan table

    @return plans
    """
    ret = []
    with utils.db_session() as session:
        if plan_id:
            query_res = session.query(models.Plan).get(plan_id)
            if not query_res:
                raise HTTPError(404, 'Plan not found')
            
            ret.append(query_res.as_dict())

        else:
            query_res = session.query(models.Plan).all()
            for result in query_res:
                ret.append(result.as_dict())

    return json.dumps(ret)

@app.route('/plans/<int:plan_id>', methods = ['DELETE'])
def delete_plans(plan_id):
    """
    Deletes a plan if specified plan has no tasks
    """
    with utils.db_session() as session:
        plan = session.query(models.Plan).get(plan_id)
        if plan:
            num_tasks = session.query(models.Task)\
                .filter(models.Task.plan_id == plan_id).count()

            if num_tasks > 0:
                raise HTTPError(403, 'Cannot delete plan with tasks')

            session.delete(plan)
    return json.dumps({'Success': True})

@app.route('/plans/<int:plan_id>/tasks', methods = ['POST'])
def create_task(plan_id):
    """
    Create a task
    @param: plan_id
    @body: json object with prod_id, and quantity

    @returns: task resource if successful
    """
    try:
        content = request.get_json()
        product = content['prod_id']
        quantity = content['quantity']
    except Exception:
        raise HTTPError(400, 'Invalid parameters for task')

    ret = []
    with utils.db_session() as session:
        query_res = session.query(models.Plan).get(plan_id)
        if not query_res:
            raise HTTPError(404, 'Plan not found')

        item = session.query(models.Inventory).get(product)
        if not item:
            raise HTTPError(400, 'Product does not exist')
        if item.quantity < quantity:
            raise HTTPError(400, 'Quantity of task exceeds central inventory')

        new_task = models.Task()
        new_task.plan_id = plan_id
        new_task.product_id = product
        new_task.target_quantity = quantity
        session.add(new_task)
        session.flush()

        ret.append(new_task.as_dict())

    return json.dumps(ret)

@app.route('/tasks')
@app.route('/tasks/<int:task_id>')
@app.route('/plans/<int:plan_id>/tasks')
def get_tasks(plan_id = None, task_id = None):
    """
    Get tasks. Can retrieve a single task, all tasks, or all tasks given
    a plan_id. If plan_id specified, return a join of plan and tasks of that
    plan.

    @param: task_id pk
    @param: plan_id pk

    @returns list of task/tasks
    """
    ret = []
    with utils.db_session() as session:
        if task_id:
            query_res = session.query(models.Task).get(task_id)
            if not query_res:
                raise HTTPError(404, 'Task id not found')
            ret.append(query_res.as_dict())

        elif plan_id:
            query_res = session.query(models.Plan, models.Task)\
                .filter(models.Plan.id == plan_id).join(models.Task)

            for plan_res, result in query_res:
                ret.append(result.as_dict())

        else:
            query_res = session.query(models.Task).all()
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
