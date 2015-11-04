import gevent.pywsgi
from sqlalchemy import func, case, literal_column
from flask import Flask, request, abort, jsonify, url_for
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
    ret = None
    with utils.db_session() as session:
        if inv_id:
            query_res = session.query(models.Inventory).get(inv_id)
            if not query_res:
                raise HTTPError(404, 'Inventory not found')
            ret = query_res.as_dict()
        else:
            query_res = session.query(models.Inventory).all()
            ret = []
            for result in query_res:
                link = url_for('get_inventory', inv_id = result.id)
                ret.append(result.as_dict(link = link))

    return json.dumps(ret)


@app.route('/plans', methods = ['POST'])
def create_plan():
     """
     create a new plan

     @return plan dict
     """
     content = request.get_json()
     name = content.get('name', None)
     if name is None:
         raise HTTPError(400, 'Plan is missing a name')

     with utils.db_session() as session:
         new_plan = models.Plan(name)
         session.add(new_plan)
         session.flush()

         link = url_for('get_plans', plan_id = new_plan.id)
         ret = new_plan.as_dict(link = link)
     return json.dumps(ret)


@app.route('/plans/<int:plan_id>')
@app.route('/plans')
def get_plans(plan_id = None):
    """
    Get all the plans.
    @param plan_id is pk of the plan table

    @return plans
    """
    ret = None
    with utils.db_session() as session:
        if plan_id:
            query_res = session.query(models.Plan).get(plan_id)
            if not query_res:
                raise HTTPError(404, 'Plan not found')

            task_base = url_for('get_tasks')
            ret = query_res.as_dict(task_base = task_base)

        else:
            query_res = session.query(models.Plan).all()
            ret = []
            for result in query_res:
                link = url_for('get_plans', plan_id = result.id)
                ret.append(result.as_dict(link = link))

    return json.dumps(ret)


@app.route('/plans/<int:plan_id>', methods = ['DELETE'])
def delete_plans(plan_id):
    """
    Deletes a plan if specified plan has no tasks
    """
    with utils.db_session() as session:
        plan = session.query(models.Plan).get(plan_id)
        if plan:
#            num_tasks = session.query(models.Task)\
#                .filter(models.Task.plan_id == plan_id).count()
#            if num_tasks > 0:

            if len(plan.tasks) > 0:
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
    content = request.get_json()
    product = content.get('prod_id', None)
    quantity = content.get('quantity', None)

    if (not isinstance(product, int) and product > 0) or \
            (not isinstance(quantity, int) and quantity > 0):
        raise HTTPError(400, 'Invalid parameters for task')

    ret = None
    with utils.db_session() as session:
        query_res = session.query(models.Plan).get(plan_id)
        if not query_res:
            raise HTTPError(404, 'Plan not found')

        item = session.query(models.Inventory).get(product)
        if not item:
            raise HTTPError(400, 'Product does not exist')
        if item.quantity < quantity:
            raise HTTPError(400, 'Quantity of task exceeds central inventory')

        new_task = models.Task(plan_id, product, quantity)
        session.add(new_task)
        session.flush()

        link = url_for('get_tasks', task_id = new_task.id)
        ret = new_task.as_dict(link = link)

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

            ret = query_res.as_dict(include_wo = True)

        elif plan_id:
            query_res = session.query(models.Plan, models.Task)\
                .filter(models.Plan.id == plan_id).join(models.Task)

            for plan_res, result in query_res:
                link = url_for('get_tasks', task_id = result.id)
                ret.append(result.as_dict(include_wo = True, link = link))

        else:
            query_res = session.query(models.Task).all()
            for result in query_res:
                link = url_for('get_tasks', task_id = result.id)
                ret.append(result.as_dict(include_wo = True, link = link))

    return json.dumps(ret)


@app.route('/tasks/<int:task_id>', methods = ['DELETE'])
def delete_task(task_id):
    """
    Deletes a specified task

    @param task_id pk
    @return success
    """

    with utils.db_session() as session:
        task = session.query(models.Task).get(task_id)
        if task:
            if task.get_status() != Status.NOTSTARTED:
                raise HTTPError(403, 'Task already started. Cannot delete active task')

            session.delete(task)

    return json.dumps({})


@app.route('/tasks/<int:task_id>', methods = ['PUT'])
def update_tasks(task_id):
    """
    Updates a task. The follow operations are allowed by the client:
    1. Reparent the task's plan
    2. Change the product id iff the task has 0 workorders
    
    @param task_id pk
    @return success status
    """

    content = request.get_json()
    new_plan_id = content.get('plan_id', None)
    new_product_id = content.get('product_id', None)
    new_target_quantity = content.get('target_quantity', None)

    if new_target_quantity and (not isinstance(new_target_quantity, int)
                                or new_target_quantity <= 0):
        raise HTTPError(400, 'Invalid target quantity')

    with utils.db_session() as session:
        task = session.query(models.Task).get(task_id)
        if not task:
            raise HTTPError(404, 'Task not found')

        if new_plan_id:
            plan = session.query(models.Plan).get(new_plan_id)
            if not plan:
                raise HTTPError(404, 'Target plan not found')

            task.plan_id = new_plan_id
            session.flush()

        else:
            if new_product_id:
                #check if existing work orders
                if len(task.work_order) > 0:
                    raise HTTPError(403, 'Task has existing work orders. Cannot alter product')

                task.product_id = new_product_id
                new_target_quantity = task.target_quantity

            if new_target_quantity:
                if not new_product_id:
                    new_product_id = task.product_id

                #check if there's enough inventory
                available_inventory = session.query(models.Inventory)\
                    .get(new_product_id)
                
                if not available_inventory or \
                        available_inventory.quantity < new_target_quantity :
                    raise HTTPError(403, 'Task has Insufficient product quantity')

                task.target_quantity = new_target_quantity

            session.flush()

        link = url_for('get_tasks', tasks_id = task_id)
        ret = task.as_dict(link = link)
        return json.dumps(ret)


@app.route('/tasks/<int:task_id>/work_order', methods = ['POST'])
def create_work_order(task_id):
    """
    Creates a new work order
    @param: task_id (pk)
    @body: json target_quantity

    @return work order    
    """

    ret = []
    content = request.get_json()
    target_quantity = content.get('target_quantity', None)
    if not isinstance(target_quantity, int) and target_quantity <= 0:
        raise HTTPError(400, 'Invalid parameters to work order')

    with utils.db_session() as session:
        total_work = func.sum(models.WorkOrder.target_quantity)\
            .label('total_wo_quantity')

        query_res = session.query(\
            models.Task, total_work)\
            .outerjoin(models.WorkOrder)\
            .filter(models.Task.id == task_id)
#        query_res = session.query(\
#            models.Task.target_quantity, models.Task.status, total_work)\
#            .outerjoin(models.WorkOrder)\
#            .filter(models.Task.id == task_id)

        for result in query_res:
            task, total_work = result
#            task_target_quantity, task_status, total_work = result
        if not total_work:
            total_work = 0

        if not task:
            raise HTTPError(404, 'Task not found')

        if task.get_status() == Status.COMPLETED:
            raise HTTPError(403, 'Task is already completed. Cannot add new work order')

        if target_quantity + total_work > task.target_quantity:
            raise HTTPError(403, 'New work order quantity greater than task total quantity')
        
        new_wo = models.WorkOrder()
        new_wo.target_quantity = target_quantity
        new_wo.task_id = task_id

        session.add(new_wo)
        session.flush()

        link = url_for('get_work_order', work_id = new_wo.id)
        ret = new_wo.as_dict(link = link)
    return json.dumps(ret)


@app.route('/work_orders/<int:work_id>', methods = ['PUT'])
def update_work_order(work_id):
    """
    Updates the quantity for a work order.

    @return updated work order
    """
    ret = []
    content = request.get_json()
    quantity = content.get('actual_quantity', None)
    completed = content.get('completed', False)

    if quantity and quantity <= 0:
        raise HTTPError(400, 'Invalid parameters to update work order')

    with utils.db_session() as session:
        wo = session.query(models.WorkOrder).get(work_id)
        if not wo:
            raise HTTPError(404, 'Work order not found')

        query_res = session.query(\
            models.Inventory,
            models.WorkOrderInventory)\
            .outerjoin(models.WorkOrderInventory)\
            .filter(models.Inventory.id == wo.task.product_id)

        wo_inventory = None
        for result in query_res:
            central_inventory, wo_inventory = result

        if wo_inventory is None:
            wo_inventory = models.WorkOrderInventory(wo.task.product_id)
            session.add(wo_inventory)

        if quantity is not None:
            #check if work order quantity can be updated / started
            quantity_diff = quantity - wo.actual_quantity

            wo_inventory.active_inventory += quantity_diff
            if wo_inventory.active_inventory > central_inventory.quantity:
               raise HTTPError(403, 'Work order cannot be started because central inventory does not have enough product')

            wo.actual_quantity = quantity

        #Update the WO status. If it was NOTSTARTED before, mark as INPROGRESS
        if wo.status == Status.NOTSTARTED:
            wo.status = Status.INPROGRESS
            wo.task.status = Status.INPROGRESS
        if completed:
            if wo.actual_quantity <= 0:
                raise HTTPError(403, 'Cannot complete work order without any product applied')
            wo.status = Status.COMPLETED

        #Determine if all the WorkOrders are completed.
        total_wo = func.count(models.WorkOrder.id)
        total_completed = func.count(case(\
                [((models.WorkOrder.status == Status.COMPLETED), models.WorkOrder.id)], else_ = literal_column("NULL"))).label("total_wo_complete")
        sum_wo_quantity = func.sum(models.WorkOrder.actual_quantity)

        query_res = session.query(total_completed, total_wo, sum_wo_quantity).filter(models.WorkOrder.task_id == wo.task.id)
        for result in query_res:
            num_complete, num_wo, total_quantity = result

        if num_complete and num_wo and num_complete == num_wo:
            #All WorkOrders are complete. Update Central Inventory
#            wo.task.status = Status.COMPLETED
            wo_inventory.active_inventory -= total_quantity
            central_inventory.quantity -= total_quantity

        session.flush()
        link = url_for('get_work_order', work_id = work_id)
        ret.append(wo.as_dict(link = link))

    return json.dumps(ret)

@app.route('/work_orders/<int:work_id>', methods = ['DELETE'])
def delete_work_order(work_id):
    """
    Delete a specified work order. Can only delete if work order has
    status: NOTSTARTED
    """

    with utils.db_session() as session:
        work_order = session.query(models.WorkOrder).get(work_id)
        if work_order:
            if work_order.status != Status.NOTSTARTED:
                raise HTTPError(403, 'Cannot delete an active work order')

            session.delete(work_order)

    return json.dumps({})

@app.route('/work_orders')
@app.route('/tasks/<int:task_id>/work_orders')
@app.route('/work_orders/<int:work_id>')
def get_work_order(work_id = None, task_id = None):
    """
    Get a specified work order

    @return request work orders
    """

    ret = []
    with utils.db_session() as session:
        if work_id:
            query_res = session.query(models.WorkOrder).get(work_id)
            if not query_res:
                raise HTTPError(404, 'Work Order not found')
            ret = query_res.as_dict()
        elif task_id:
            query_res = session.query(models.WorkOrder)\
                .filter(models.Task.id == task_id).join(models.Task)
            for result in query_res:
                link = url_for('get_work_order', work_id = result.id)
                ret.append(result.as_dict(link = link))
        else:
            query_res = session.query(models.WorkOrder).all()
            for result in query_res:
                link = url_for('get_work_order', work_id = result.id)
                ret.append(result.as_dict(link = link))

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
