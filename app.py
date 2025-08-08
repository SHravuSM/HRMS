import os
import csv
import math
import sqlite3
import logging
from io import StringIO
from pytz import timezone
import uuid
from datetime import datetime, date
from database import Database
from werkzeug.utils import secure_filename
from flask import Flask, Response, current_app, render_template, request, redirect, send_from_directory, url_for, session, flash, jsonify, abort

# Configure logging to a file
logging.basicConfig(
    filename="error.log",                # Log file name
    level=logging.ERROR,                 # Only log errors and above
    format="%(asctime)s [%(levelname)s] %(message)s",  # Log format
)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
db = Database()

app.config['SECRET_KEY'] = 'your-secret-key-here'
POLICIES_FOLDER = 'Policies'
os.makedirs(POLICIES_FOLDER, exist_ok=True)

UPLOAD_FOLDER = 'static/bngImg'
INVOICE_FOLDER = 'static/invoices'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Add these constants at the top of app.py
POLICIES_FOLDER = 'policies'
ALLOWED_EXTENSIONS = {'pdf'}

def ensure_policies_folder():
    """Create the policies folder if it doesn't exist."""
    if not os.path.exists(POLICIES_FOLDER):
        os.makedirs(POLICIES_FOLDER)

def policy_name_exists(policy_name):
    """Check if a policy with the given name already exists."""
    return db.policy_exists(policy_name)


def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(original_filename):
    """Generate a unique filename with timestamp prefix."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    file_extension = os.path.splitext(original_filename)[1]
    return f"{timestamp}_{unique_id}{file_extension}"
    
def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.template_filter('todate')
def todate(value):
    """Jinja2 filter: given a datetime-string or datetime, return its date."""
    if not value:
        return ''
    
    if isinstance(value, datetime):
        return value.date()
    
    s = str(value).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    
    try:
        return datetime.strptime(s[:10], '%Y-%m-%d').date()
    except Exception:
        return s

@app.template_filter('todate')
def todate(value):
    """
    Jinja2 filter: given a datetime-string or datetime, return its date.
    Handles both 'YYYY-MM-DD HH:MM:SS' and 'YYYY-MM-DD'.
    """
    if not value:
        return ''
    # If it's already a datetime
    if isinstance(value, datetime):
        return value.date()

    s = str(value).strip()
    # Try full-timestamp first
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Fallback: just take first 10 chars as date
    try:
        return datetime.strptime(s[:10], '%Y-%m-%d').date()
    except Exception:
        return s  # give up, return raw

def get_db_connection():
    conn = sqlite3.connect('project_tracking.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        if session['emp_type'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('employee_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form['data']
        password = request.form['password']

        user = db.verify_user(data, password)
        
        if user:
            session['user_id'] = user[0]
            session['first_name'] = user[1]
            session['last_name'] = user[2]
            session['emp_type'] = user[3]
            
            if user[3] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('employee_dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    # Pagination parameters
    page = int(request.args.get('page', 1))
    page_size = 10
    project_filter = request.args.get('project_filter', '')
    status_filter = request.args.get('status_filter', '')
    employee_filter = request.args.get('employee_filter', '')
    
    # Get paginated tasks and total task count
    tasks, total_tasks = db.get_all_tasks_with_details_paginated(page, page_size, project_filter, status_filter, employee_filter)
    employees = db.get_employees()
    projects = db.get_projects()
    
    # Calculate total pages
    total_pages = math.ceil(total_tasks / page_size)
    
    return render_template('admin_dashboard.html', 
                         tasks=tasks, 
                         employees=employees, 
                         projects=projects, 
                         page=page, 
                         page_size=page_size, 
                         total_tasks=total_tasks, 
                         total_pages=total_pages,
                         project_filter=project_filter,
                         status_filter=status_filter,
                         employee_filter=employee_filter)

@app.route('/admin/view_employees')
def view_employees():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    status_filter = request.args.get('status_filter', 'all')
    employees = db.get_employees(status_filter=status_filter)
    
    return render_template('view_employees.html', employees=employees, status_filter=status_filter)

@app.route('/admin/edit_employee/<int:emp_id>', methods=['GET', 'POST'])
def edit_employee(emp_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    employee = db.get_employee(emp_id)
    if not employee:
        flash('Employee not found.', 'error')
        return redirect(url_for('view_employees'))
    
    if request.method == 'POST':
        employee_data = {
            'first_name': request.form['first_name'],
            'last_name': request.form['last_name'],
            'gender': request.form['gender'],
            'dob': request.form['dob'],
            'address': request.form['address'],
            'phone_no': request.form['phone_no'],
            'email': request.form['email'],
            'password': request.form['password'],
            'status': request.form['status'],
            'emp_type': request.form['emp_type']
        }
        
        try:
            db.update_employee(emp_id, employee_data)
            flash('Employee updated successfully!', 'success')
            return redirect(url_for('view_employees'))
        except Exception as e:
            flash('Error updating employee. Email might already exist.', 'error')
    
    return render_template('edit_employee.html', employee=employee)

@app.route('/admin/delete_employee/<int:emp_id>')
def delete_employee(emp_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        db.delete_employee(emp_id)
        flash('Employee deleted successfully!', 'success')
    except Exception as e:
        flash(str(e), 'error')
    
    return redirect(url_for('view_employees'))

@app.route('/admin/add_employee', methods=['GET', 'POST'])
def add_employee():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        employee_data = {
            'first_name': request.form['first_name'],
            'last_name': request.form['last_name'],
            'gender': request.form['gender'],
            'dob': request.form['dob'],
            'address': request.form['address'],
            'phone_no': request.form['phone_no'],
            'email': request.form['email'],
            'password': request.form['password'],
            'status': request.form['status'],
            'emp_type': request.form['emp_type']
        }
        
        try:
            emp_id = db.add_employee(employee_data)
            flash('Employee added successfully!', 'success')
            return redirect(url_for('manage_profile', emp_id=emp_id))
        except Exception as e:
            flash('Error adding employee. Email might already exist.', 'error')
    
    return render_template('add_employee.html')

@app.route('/admin/view_projects')
def view_projects():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    projects = db.get_projects()
    return render_template('view_projects.html', projects=projects)

@app.route('/admin/view_project/<int:project_id>')
def view_project(project_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    project = db.get_project(project_id)
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('view_projects'))
    
    tasks = db.get_tasks_by_project(project_id)
    return render_template('view_project.html', project=project, tasks=tasks)

@app.route('/admin/edit_project/<int:project_id>', methods=['GET', 'POST'])
def edit_project(project_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    project = db.get_project(project_id)
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('view_projects'))
    
    if request.method == 'POST':
        project_data = {
            'project_name': request.form['project_name'],
            'priority': request.form['priority'],
            'project_desc': request.form['project_desc'],
            'project_status': request.form['project_status'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date']
        }
        
        try:
            db.update_project(project_id, project_data)
            flash('Project updated successfully!', 'success')
            return redirect(url_for('view_projects'))
        except Exception as e:
            flash('Error updating project.', 'error')
    
    return render_template('edit_project.html', project=project)

@app.route('/admin/delete_project/<int:project_id>')
def delete_project(project_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        db.delete_project(project_id)
        flash('Project deleted successfully!', 'success')
    except Exception as e:
        flash(str(e), 'error')
    
    return redirect(url_for('view_projects'))

@app.route('/admin/add_project', methods=['GET', 'POST'])
def add_project():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        project_data = {
            'project_name': request.form['project_name'],
            'priority': request.form['priority'],
            'project_desc': request.form['project_desc'],
            'project_status': request.form['project_status'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date']
        }
        
        try:
            db.add_project(project_data)
            flash('Project added successfully!', 'success')
            return redirect(url_for('view_projects'))
        except Exception as e:
            flash('Error adding project.', 'error')
    
    return render_template('add_project.html')

@app.route('/admin/view_tasks')
def view_tasks():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    # Pagination parameters
    page = int(request.args.get('page', 1))
    page_size = 10
    project_filter = request.args.get('project_filter', '')
    status_filter = request.args.get('status_filter', '')
    employee_filter = request.args.get('employee_filter', '')
    
    # Get paginated tasks and total task count
    tasks, total_tasks = db.get_all_tasks_with_details_paginated(page, page_size, project_filter, status_filter, employee_filter)
    employees = db.get_employees()
    projects = db.get_projects()
    
    # Calculate total pages
    total_pages = math.ceil(total_tasks / page_size)
    
    return render_template('view_tasks.html', 
                         tasks=tasks, 
                         employees=employees, 
                         projects=projects, 
                         page=page, 
                         page_size=page_size, 
                         total_tasks=total_tasks, 
                         total_pages=total_pages,
                         project_filter=project_filter,
                         status_filter=status_filter,
                         employee_filter=employee_filter)

@app.route('/admin/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    task = db.get_task(task_id)
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('view_tasks'))
    
    if request.method == 'POST':
        task_data = {
            'project_id': request.form['project_id'],
            'emp_id': request.form['emp_id'],
            'task_desc': request.form['task_desc'],
            'priority': request.form['priority'],
            'status': request.form['status'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date']
        }
        
        try:
            db.update_task(task_id, task_data)
            flash('Task updated successfully!', 'success')
            return redirect(url_for('view_tasks'))
        except Exception as e:
            flash('Error updating task.', 'error')
    
    projects = db.get_projects()
    employees = db.get_employees()
    return render_template('edit_task.html', task=task, projects=projects, employees=employees)

@app.route('/admin/delete_task/<int:task_id>')
def delete_task(task_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        db.delete_task(task_id)
        flash('Task deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting task.', 'error')
    
    return redirect(url_for('view_tasks'))

@app.route('/admin/add_task', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        task_data = {
            'project_id': request.form['project_id'],
            'emp_id': request.form['emp_id'],
            'task_desc': request.form['task_desc'],
            'priority': request.form['priority'],
            'status': request.form['status'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date']
        }

        try:
            db.add_task(task_data)
            flash('Task added successfully!', 'success')
            return redirect(url_for('view_tasks'))
        except Exception as e:
            flash('Error adding task.', 'error')

    projects = db.get_projects()
    employees = db.get_employees()
    today = date.today().isoformat()  # format: 'YYYY-MM-DD'
    return render_template('add_task.html', projects=projects, employees=employees, today=today)

@app.route('/employee/dashboard')
def employee_dashboard():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))

    profile = db.get_employee_profile(session['user_id'])

    # 🔐 Restrict sidebar if:
    # - EmgContact is blank
    # - OR employee never updated it
    emg_missing = (
        not profile
        or not profile.get('EmgContact')
        or profile.get('EmgUpdatedByEmp') == 0
    )

    session['emg_missing'] = emg_missing  # Used by base.html sidebar

    status_filter = request.args.get('status_filter', 'all')
    tasks = db.get_tasks_by_employee(session['user_id'], status_filter=status_filter)
    today = date.today()  # Get current date
    return render_template('employee_dashboard.html', tasks=tasks, emg_missing=emg_missing, status_filter=status_filter, today=today)

@app.route('/employee/my_profile', methods=['GET', 'POST'])
def employee_profile_view():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))

    emp_id = session['user_id']
    employee = db.get_employee(emp_id)
    profile = db.get_employee_profile(emp_id)
    alert_msg = None  # This will be passed as a flash or query param

    if request.method == 'POST':
        new_password = request.form.get('password', '').strip()
        new_emg = request.form.get('EmgContact', '').strip()

        alert_msg = db.update_employee_password_and_emgcontact(emp_id, new_password, new_emg)
        # if new_password:
        #     db.update_employee_password(emp_id, new_password)
        #     alert_msg = 'Password updated successfully.'

        # if profile:
        #     current_emg = profile.get('EmgContact', '')
        #     already_updated = profile.get('EmgUpdatedByEmp', 0)

        #     if new_emg:
        #         if already_updated:
        #             alert_msg = 'You have already updated your emergency contact once.'
        #         if not new_emg.isdigit() or len(new_emg) != 10:
        #             alert_msg = 'Emergency contact must be a 10-digit number.'
        #         elif new_emg == employee[6]:  # assuming employee[6] is mobile number
        #             alert_msg = 'Emergency contact cannot be the same as your mobile number.'
        #         else:
        #             updated = db.update_employee_emg_contact_once(emp_id, new_emg)
        #             if updated:
        #                 alert_msg = 'Emergency contact updated successfully.'
        #             else:
        #                 alert_msg = 'Update failed. Please contact admin.'
        #     else:
        #         alert_msg = 'Emergency contact cannot be blank.'

        # Flash message or pass via query string for dashboard
        flash(alert_msg)  # Requires flash setup in app
        return redirect(url_for('employee_dashboard'))

    return render_template('my_profile.html', employee=employee, profile=profile, alert_msg=alert_msg)

@app.route('/admin/employee_profile/<int:emp_id>', methods=['GET', 'POST'])
def manage_profile(emp_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    employee = db.get_employee(emp_id)
    if not employee:
        flash("Employee not found", "error")
        return redirect(url_for('view_employees'))

    profile = db.get_employee_profile(emp_id)

    if request.method == 'POST':
        data = {
            'EmployeeId': emp_id,
            'UANNo': request.form['UANNo'],
            'PANNO': request.form['PANNO'],
            'AadharNo': request.form['AadharNo'],
            'BankName': request.form['BankName'],
            'BranchName': request.form['BranchName'],
            'ACNo': request.form['ACNo'],
            'IFSCode': request.form['IFSCode'],
            'Designation': request.form['Designation'],
            'EmgContact': request.form['EmgContact'],
            'ReportingMng': request.form['ReportingMng'],
            'DOJ': request.form['DOJ'],
            'PrgLng': request.form['PrgLng'],
            'FrmWrk': request.form['FrmWrk']
        }
        if profile:
            db.update_employee_profile(emp_id, data)
        else:
            db.add_employee_profile(data)
        flash("Profile saved", "success")
        return redirect(url_for('view_employees'))
        

    return render_template('employee_profile.html', employee=employee, profile=profile)

@app.route('/employee/add_task_detail', methods=['POST'])
def add_task_detail():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    
    task_id = request.form['task_id']
    desc = request.form['desc']
    status = request.form['status']
    
    try:
        # Check if an update already exists for today
        if db.has_task_detail_today(task_id, session['user_id']):
            flash('You have already added an update for this task today.', 'error')
            return redirect(url_for('view_task_details', task_id=task_id))
        
        db.add_task_detail(task_id, desc, status, session['user_id'])
        flash('Task update added successfully!', 'success')
    except Exception as e:
        flash('Error adding task update.', 'error')
    
    return redirect(url_for('view_task_details', task_id=task_id))

@app.route('/employee/view_task_details/<int:task_id>')
def view_task_details(task_id):
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    
    task = db.get_task(task_id)
    if not task or task[3] != session['user_id']:  # Ensure task belongs to the employee
        flash('Task not found or you do not have permission to view it.', 'error')
        return redirect(url_for('employee_dashboard'))
    
    details = db.get_task_details_by_employee(task_id, session['user_id'])
    project = db.get_project(task[2])  # Get project details for task
    return render_template('view_task_details.html', task=task, details=details, project=project)

@app.route('/employee/edit_task_detail/<int:detail_id>', methods=['GET', 'POST'])
def edit_task_detail(detail_id):
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    
    detail = db.get_task_detail(detail_id)
    if not detail or not db.verify_task_detail_owner(detail_id, session['user_id']):
        flash('Task update not found or you do not have permission to edit it.', 'error')
        return redirect(url_for('employee_dashboard'))
    
    if request.method == 'POST':
        desc = request.form['desc']
        status = request.form['status']
        
        try:
            db.update_task_detail(detail_id, desc, status)
            flash('Task update edited successfully!', 'success')
            return redirect(url_for('view_task_details', task_id=detail[1]))
        except Exception as e:
            flash('Error editing task update.', 'error')
    
    return render_template('edit_task_detail.html', detail=detail, task_id=detail[1])

@app.route('/api/task_details/<int:task_id>')
def get_task_details(task_id):
    try:
        if 'user_id' not in session:
            logger.warning(f"Unauthorized access attempt to task details for task_id {task_id}")
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Verify task exists
        task = db.get_task(task_id)
        if not task:
            logger.warning(f"Task not found for task_id {task_id}")
            return jsonify({'error': 'Task not found'}), 404
        
        details = db.get_task_details(task_id)
        
        # Convert to list of dictionaries for JSON response
        details_list = []
        for detail in details:
            details_list.append({
                'detail_id': detail[0],
                'desc': detail[1],
                'inserted_date': detail[2] if detail[2] else None,  # Handle null dates
                'status': detail[3]
            })
        
        logger.debug(f"Successfully fetched {len(details_list)} task details for task_id {task_id}")
        return jsonify(details_list)
    
    except Exception as e:
        logger.error(f"Error in get_task_details for task_id {task_id}: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

@app.route('/admin/show_task_details/<int:task_id>')
def show_task_details(task_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    task = db.get_task(task_id)
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    project = db.get_project(task[2])  # task[2] is project_id
    employee = db.get_employee(task[3])  # task[3] is emp_id
    task_details = db.get_task_details(task_id)  # Use existing get_task_details method
    
    return render_template('show_task_details.html', task=task, project=project, employee=employee, task_details=task_details)

# ------ Leave types ----------------------------------
@app.route('/admin/leave_types', methods=['GET', 'POST'])
def admin_leave_types():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    popup_message = None
    popup_type = None

    if request.method == 'POST':
        leave_type = request.form['leave_type'].strip()
        lt_id = request.form.get('leave_type_id')

        if not leave_type:
            popup_message = 'Leave type cannot be empty.'
            popup_type = 'error'
        elif lt_id:  # Edit
            success = db.update_leave_type(int(lt_id), leave_type)
            popup_message = 'Leave type updated successfully.' if success else 'Update failed.'
            popup_type = 'success' if success else 'error'
        else:  # Add
            success, message = db.add_leave_type(leave_type)
            popup_message = message
            popup_type = 'success' if success else 'error'

    edit_type = None
    edit_id = request.args.get('edit_id')
    if edit_id:
        leave_types_all = db.get_leave_types()
        edit_type = next((lt for lt in leave_types_all if str(lt[0]) == edit_id), None)
    else:
        leave_types_all = db.get_leave_types()

    return render_template('admin_leave_types.html',
                           leave_types=leave_types_all,
                           popup_message=popup_message,
                           popup_type=popup_type,
                           edit_type=edit_type)

@app.route('/admin/delete_leave_type/<int:lt_id>')
def delete_leave_type(lt_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    db.delete_leave_type(lt_id)
    flash('Leave type deleted', 'success')
    return redirect(url_for('admin_leave_types'))

# ------ Leave requests list & approval ---------------

@app.route('/admin/employee_celebrations')
def admin_employee_celebrations():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    filter_type = request.args.get('filter', 'anniversary')  # default to anniversary
    
    # Get celebrations data
    celebrations = db.get_employee_anniversaries(filter_type)
    today_celebrations = db.get_today_celebrations()
    
    return render_template('employee_celebrations.html', 
                         celebrations=celebrations,
                         today_celebrations=today_celebrations,
                         filter_type=filter_type)

@app.route('/employee/celebrations')
def employee_celebrations():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    
    filter_type = request.args.get('filter', 'anniversary')
    
    # Get celebrations data
    celebrations = db.get_employee_anniversaries(filter_type)
    today_celebrations = db.get_today_celebrations()
    
    return render_template('employee_celebrations.html', 
                         celebrations=celebrations,
                         today_celebrations=today_celebrations,
                         filter_type=filter_type,
                         is_employee=True)

@app.route('/admin/leave_requests')
def admin_leave_requests():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    # Pagination
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    # Filter parameters
    employee_id = request.args.get('employee', '').strip()
    leave_type_id = request.args.get('type', '').strip()
    status = request.args.get('status', '').strip()
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    
    # Sorting parameters
    sort_by = request.args.get('sort_by', 'inserted_date')
    sort_order = request.args.get('sort_order', 'DESC')

    # Convert empty strings to None
    filters = {
        'employee_id': employee_id if employee_id else None,
        'leave_type_id': leave_type_id if leave_type_id else None,
        'status': status if status else None,
        'from_date': from_date if from_date else None,
        'to_date': to_date if to_date else None,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'limit': per_page,
        'offset': offset
    }

    # Get filtered and sorted results
    requests, total = db.get_leave_requests_with_advanced_filters(**filters)
    total_pages = math.ceil(total / per_page)

    # Get options for dropdowns
    employees = db.get_employees(status_filter='active')
    leave_types = db.get_leave_types()

    return render_template('admin_leave_requests.html',
                         requests=requests,
                         page=page,
                         total_pages=total_pages,
                         total_requests=total,
                         employees=employees,
                         leave_types=leave_types,
                         # Pass current filter values back to template
                         current_employee=employee_id,
                         current_type=leave_type_id,
                         current_status=status,
                         current_from_date=from_date,
                         current_to_date=to_date,
                         current_sort_by=sort_by,
                         current_sort_order=sort_order)

@app.route('/admin/leave_requests/<int:req_id>/<action>')
def update_leave_request(req_id, action):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    if action not in ('approved', 'rejected'):
        abort(400)
    db.update_leave_status(req_id, action, session['user_id'])
    flash(f'Request {action}', 'success')
    return redirect(url_for('admin_leave_requests'))

@app.route('/employee/leave', methods=['GET', 'POST'])
def employee_leave():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = {
            'leave_type_id': request.form['leave_type_id'],
            'employee_id':   session['user_id'],
            'start_date':    request.form['start_date'],
            'end_date':      request.form['end_date'],
            'leave_desc':    request.form['leave_desc'][:500],
            'manager_id':    None,                 # set later if you have manager mapping
        }
        db.add_leave_request(data)
        flash('Leave request submitted', 'success')
        return redirect(url_for('employee_leave_requests'))

    leave_types = db.get_leave_types()
    my_requests = db.get_leave_requests('WHERE lr.employee_id=?', (session['user_id'],))
    print(my_requests)
    today_iso    = date.today().isoformat()          #  ← new

    return render_template('employee_leave.html',
                           leave_types=leave_types, my_requests=my_requests, today=today_iso                          #  ← new
)

@app.route('/employee/delete_leave_request/<int:request_id>', methods=['POST'])
def delete_leave_request(request_id):
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    
    db.delete_leave_request(request_id)
    flash('Leave request deleted', 'success')
    return redirect(url_for('employee_leave_requests'))

@app.route('/employee/delete_expense/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
        
    db.delete_expense(expense_id)
    flash('Expense deleted', 'success')
    return redirect(url_for('existing_expenses'))

@app.route('/employee/my_leave_requests')
def employee_leave_requests():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    my_requests = db.get_leave_requests('WHERE lr.employee_id=?', (session['user_id'],))
    return render_template('employee_leave_requests.html', my_requests=my_requests)
    
@app.route('/admin/expense_types', methods=['GET', 'POST'])
def admin_expense_types():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        etype = request.form['expense_type'].strip().title()
        if etype:
            db.add_expense_type(etype)
            msg = f'Expense type "{etype}" saved (duplicates are ignored)'
            return redirect(url_for('admin_expense_types', msg=msg))

    types_ = db.get_expense_types()
    msg = request.args.get('msg')
    return render_template('admin_expense_types.html', types=types_, msg=msg)

@app.route('/admin/delete_expense_type/<int:et_id>')
def delete_expense_type(et_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    db.delete_expense_type(et_id)
    flash('Expense type deleted', 'success')
    return redirect(url_for('admin_expense_types'))

@app.route('/admin/edit_expense_type/<int:et_id>', methods=['POST'])
def edit_expense_type(et_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    new_type = request.form['new_expense_type'].strip().title()
    if new_type:
        if db.expense_type_exists(new_type, exclude_id=et_id):
            flash(f'Expense type "{new_type}" already exists.', 'error')
        else:
            db.update_expense_type(et_id, new_type)
            flash(f'Expense type updated to "{new_type}"', 'success')

    return redirect(url_for('admin_expense_types'))

@app.route('/expense', methods=['GET', 'POST'])
def expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        expense_date = request.form['expense_date']
        employee_id = (
            request.form['employee_id']
            if session['emp_type'] == 'admin'
            else session['user_id']
        )
        invoice_path = None
        if 'invoice_file' in request.files:
            file = request.files['invoice_file']
            if file and file.filename:
                filename = secure_filename(file.filename)
                invoice_path = os.path.join(INVOICE_FOLDER, filename).replace('\\', '/')
                file.save(invoice_path)

        data = {
            'expense_type_id': request.form['expense_type_id'],
            'employee_id':     employee_id,
            'exp_description': request.form['exp_description'][:500],
            'manager_id':      None,
            'approver_comments': '',
            'given_by_id':     None,
            'final_comments':  '',
            'amount': float(request.form['amount']),
            'expense_date': expense_date
        }

        data['invoice_path'] = invoice_path
        db.add_expense(data)
        flash('Expense submitted', 'success')
        return redirect(url_for('existing_expenses'))

    types_ = db.get_expense_types()
    employees = db.get_employees(status_filter='active') if session['emp_type'] == 'admin' else []
    return render_template('expense.html', types=types_, employees=employees)

@app.route('/existing_expenses')
def existing_expenses():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    page = int(request.args.get('page', 1))
    per_page = 15
    offset = (page - 1) * per_page

    filters = []
    params = []

    employee_id = request.args.get('employee_id', '').strip()
    expense_type = request.args.get('expense_type', '').strip()
    status = request.args.get('status', '').strip()
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()

    ist = timezone('Asia/Kolkata')  # IST timezone

    if session['emp_type'] == 'admin':
        if employee_id:
            filters.append("ex.employee_id = ?")
            params.append(employee_id)
        if expense_type:
            filters.append("et.expense_type = ?")
            params.append(expense_type)
        if status:
            filters.append("ex.status = ?")
            params.append(status)
        if from_date:
            filters.append("DATE(ex.inserted_date) >= ?")
            params.append(from_date)
        if to_date:
            filters.append("DATE(ex.inserted_date) <= ?")
            params.append(to_date)

        where_clause = 'WHERE ' + ' AND '.join(filters) if filters else ''
        total = db.count_expenses(where_clause, tuple(params))
        expenses = db.get_expenses_paginated(where_clause, tuple(params), per_page, offset)
        expense_types = db.get_expense_types()
        employees = db.get_employees(status_filter='active')

    else:
        base = "WHERE ex.employee_id = ?"
        params = [session['user_id']]
        if status:
            base += " AND ex.status = ?"
            params.append(status)
        if from_date:
            base += " AND DATE(ex.inserted_date) >= ?"
            params.append(from_date)
        if to_date:
            base += " AND DATE(ex.inserted_date) <= ?"
            params.append(to_date)

        total = db.count_expenses(base, tuple(params))
        expenses = db.get_expenses_paginated(base, tuple(params), per_page, offset)
        expense_types = []
        employees = []

    # Indices from your table structure
    IDX_INSERTED_DATE = 7
    IDX_APPROVED_DATE = 10

    # Convert tuple → list and adjust date/time
    converted_expenses = []
    for e in expenses:
        e = list(e)  # Make it mutable
        try:
            if e[IDX_INSERTED_DATE]:
                utc_time = datetime.fromisoformat(e[IDX_INSERTED_DATE])
                e[IDX_INSERTED_DATE] = utc_time.astimezone(ist).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass

        try:
            if e[IDX_APPROVED_DATE]:
                utc_time = datetime.fromisoformat(e[IDX_APPROVED_DATE])
                e[IDX_APPROVED_DATE] = utc_time.astimezone(ist).strftime('%Y-%m-%d %H:%M:%S')
            else:
                e[IDX_APPROVED_DATE] = 'Not set'
        except Exception:
            e[IDX_APPROVED_DATE] = 'Not set'

        converted_expenses.append(e)

    total_pages = math.ceil(total / per_page)
    print(converted_expenses)
    return render_template('existing_expenses.html',
                           expenses=converted_expenses,
                           expense_types=expense_types,
                           employees=employees,
                           page=page,
                           status=status,
                           total_pages=total_pages)

@app.route('/export_expenses')
def export_expenses():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    expenses = db.get_expenses()  # Use all data, no filter

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(['SlNo', 'ExpType', 'ExpnDate', 'Amt', 'Name', 'ReqDate', 'Status', 'ApprovedBy', 'Comments'])

    for i, ex in enumerate(expenses, start=1):
        writer.writerow([
            i,
            ex[1],                                # ExpType
            ex[11] or '',                         # ExpnDate
            ex[8],                                # Amount
            ex[2],                                # Name
            ex[7],                                # ReqDate
            ex[4],                                # Status
            ex[12] if len(ex) > 12 else '',       # ApprovedBy (added to SELECT)
            ex[5] or ''                           # Comments
        ])

    # Send response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            "Content-Disposition": "attachment; filename=expenses_export.csv"
        }
    )

@app.route('/api/expense/<int:exp_id>')
def get_expense_detail(exp_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    exp = db.get_expense_by_id(exp_id)
    if not exp:
        return jsonify({'error': 'Not found'}), 404

    ist = timezone('Asia/Kolkata')

    # Handle requested_date
    try:
        if exp[7]:
            req_dt = datetime.fromisoformat(exp[7]).astimezone(ist).strftime('%Y-%m-%d %H:%M:%S')
        else:
            req_dt = 'Not set'
    except Exception:
        req_dt = exp[7]
    
    # Handle approved_date
    try:
        if exp[10]:
            app_dt = datetime.fromisoformat(exp[10]).astimezone(ist).strftime('%Y-%m-%d %H:%M:%S')
        else:
            app_dt = 'Not set'
    except Exception:
        app_dt = 'Not set'

    return jsonify({
        'expense_id': exp[0],
        'type': exp[1],
        'emp_name': exp[2],
        'description': exp[3],
        'status': exp[4],
        'approver_comments': exp[5],
        'final_comments': exp[6],
        'requested_date': req_dt,
        'amount': exp[8],
        'employee_id': exp[9],
        'approved_date': app_dt,
        'approved_by': exp[11] if exp[11] else 'Not set'
    })

@app.route('/admin/expense/<int:exp_id>/<action>', methods=['POST'])
def expense_approve(exp_id, action):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    if action not in ('approved', 'rejected'):
        abort(400)

    comments = request.form.get('approver_comments', '')[:200]
    approved_by = request.form.get('approved_by', '').strip() or None
    db.update_expense_status(exp_id, action, comments, session['user_id'], approved_by)
    flash(f'Expense {action}', 'success')
    return redirect(url_for('existing_expenses'))

@app.route('/admin/leave_summary', methods=['GET', 'POST'])
def admin_leave_summary():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    # ---------- Grab filter values ----------
    f_date_from   = request.form.get('date_from')         if request.method == 'POST' else ''
    f_date_to     = request.form.get('date_to')           if request.method == 'POST' else ''
    f_leave_type  = request.form.get('leave_type_id')     if request.method == 'POST' else ''

    leave_types   = db.get_leave_types()
    summary       = db.get_leave_summary(
                        date_from   = f_date_from or None,
                        date_to     = f_date_to   or None,
                        leave_type_id = f_leave_type or None
                    )

    return render_template('admin_leave_summary.html',
                           leave_types = leave_types,
                           summary     = summary,
                           f_date_from = f_date_from,
                           f_date_to   = f_date_to,
                           f_leave_type= f_leave_type)

@app.route('/admin/leave_requests/handle', methods=['POST'])
def handle_leave_action():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    req_id = request.form['request_id']
    action = request.form['action']
    comments = request.form['comments'][:200]

    current_status = db.get_leave_status(req_id)
    if current_status != 'pending':
        flash('Action not allowed. Leave request already processed.', 'error')
        return redirect(url_for('admin_leave_requests'))

    db.update_leave_status(req_id, action, session['user_id'], comments)
    flash(f'Leave request {action}', 'success')
    return redirect(url_for('admin_leave_requests'))

@app.route('/admin/add_job', methods=['GET', 'POST'])
def add_job():
    if request.method == 'POST':
        jobtitle = request.form['jobtitle']
        exp = request.form['exp']
        sal = request.form['sal']
        location = request.form['location']
        desc = request.form['desc']
        file = request.files['banner']
        filename = ''

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        conn.execute('INSERT INTO TblCareers (JobTitle, Exp, Sal, Location, Description, BannerImg) VALUES (?, ?, ?, ?, ?, ?)',
                     (jobtitle, exp, sal, location, desc, filename))
        conn.commit()
        conn.close()
        return redirect(url_for('view_jobs'))
    return render_template('add_job.html')

@app.route('/admin/view_jobs')
def view_jobs():
    conn = get_db_connection()
    jobs = conn.execute('SELECT * FROM TblCareers').fetchall()
    conn.close()
    return render_template('view_jobs.html', jobs=jobs)

@app.route('/admin/delete_job/<int:id>')
def delete_job(id):
    conn = get_db_connection()
    job = conn.execute('SELECT BannerImg FROM TblCareers WHERE CareerId = ?', (id,)).fetchone()

    if job and job['BannerImg']:
        img_path = os.path.join(current_app.root_path, 'static', 'bngImg', job['BannerImg'])
        if os.path.exists(img_path):
            os.remove(img_path)

    conn.execute('DELETE FROM TblCareers WHERE CareerId = ?', (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('view_jobs'))

@app.route('/admin/edit_job/<int:id>', methods=['GET', 'POST'])
def edit_job(id):
    conn = get_db_connection()
    job = conn.execute('SELECT * FROM TblCareers WHERE CareerId = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        jobtitle = request.form['jobtitle']
        exp = request.form['exp']
        sal = request.form['sal']
        location = request.form['location']
        desc = request.form['desc']
        file = request.files['banner']
        filename = job['BannerImg']

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn.execute('UPDATE TblCareers SET JobTitle=?, Exp=?, Sal=?, Location=?, Description=?, BannerImg=? WHERE CareerId=?',
                     (jobtitle, exp, sal, location, desc, filename, id))
        conn.commit()
        conn.close()
        return redirect(url_for('view_jobs'))
    
    conn.close()
    return render_template('edit_job.html', job=job)

@app.route('/employee/careers')
def employee_careers():
    conn = get_db_connection()
    jobs = conn.execute('SELECT * FROM TblCareers').fetchall()
    conn.close()
    return render_template('employee_careers.html', jobs=jobs)

@app.route('/admin/add_asset', methods=['GET', 'POST'])
def add_asset():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO TblAssets (ItemName, Model, Price, Descriptions, Status) VALUES (?, ?, ?, ?, ?)',
                     (request.form['item_name'], request.form['model'], request.form['price'], request.form['descriptions'], request.form['status']))
        conn.commit()
        conn.close()
        flash('Asset added successfully!', 'success')
        return redirect(url_for('view_assets'))
    return render_template('add_asset.html')

@app.route('/admin/view_assets')
def view_assets():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    assets = conn.execute('SELECT * FROM TblAssets').fetchall()
    conn.close()
    return render_template('view_assets.html', assets=assets)

@app.route('/admin/edit_asset/<int:asset_id>', methods=['GET', 'POST'])
def edit_asset(asset_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    asset = conn.execute('SELECT * FROM TblAssets WHERE AssetId = ?', (asset_id,)).fetchone()
    if request.method == 'POST':
        conn.execute('UPDATE TblAssets SET ItemName=?, Model=?, Price=?, Descriptions=?, Status=? WHERE AssetId=?',
                     (request.form['item_name'], request.form['model'], request.form['price'], request.form['descriptions'], request.form['status'], asset_id))
        conn.commit()
        conn.close()
        flash('Asset updated successfully!', 'success')
        return redirect(url_for('view_assets'))
    conn.close()
    return render_template('edit_asset.html', asset=asset)

@app.route('/admin/delete_asset/<int:asset_id>')
def delete_asset(asset_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM TblAssets WHERE AssetId = ?', (asset_id,))
    conn.commit()
    conn.close()
    flash('Asset deleted successfully!', 'success')
    return redirect(url_for('view_assets'))

@app.route('/admin/allocate_asset', methods=['GET', 'POST'])
def allocate_asset():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    assets = conn.execute("SELECT * FROM TblAssets WHERE Status = 'Available'").fetchall()
    employees = conn.execute("SELECT emp_id, first_name, last_name FROM tbl_employee WHERE status = 'active'").fetchall()

    selected_asset_id = request.args.get('asset_id', type=int)

    if request.method == 'POST':
        conn.execute('''
            INSERT INTO TblAllocateAssets (AssetId, EmployeeId, AllocateDate, Status, AllocatedBy, Description)
            VALUES (?, ?, DATE('now'), 'Allocated', ?, ?)
        ''', (
            request.form['asset_id'],
            request.form['employee_id'],
            request.form['allocated_by'],
            request.form['description']
        ))
        conn.execute("UPDATE TblAssets SET Status = 'Allocated' WHERE AssetId = ?", (request.form['asset_id'],))
        conn.commit()
        conn.close()
        flash("Asset allocated successfully", "success")
        return redirect(url_for('manage_allocation'))

    return render_template(
        'allocate_asset.html',
        assets=assets,
        employees=employees,
        selected_asset_id=selected_asset_id
    )

@app.route('/admin/manage_allocation')
def manage_allocation():
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT aa.*, a.ItemName, a.Model, e.first_name, e.last_name,
            (
                SELECT GROUP_CONCAT(IssueId || '##' || IssueText, '||')
                FROM TblAssetIssues
                WHERE AssetId = aa.AssetId AND EmployeeId = aa.EmployeeId AND Status = 'Open'
            ) AS Issues
        FROM TblAllocateAssets aa
        JOIN TblAssets a ON aa.AssetId = a.AssetId
        JOIN tbl_employee e ON aa.EmployeeId = e.emp_id
        ORDER BY aa.AllocateDate DESC
    ''').fetchall()
    return render_template('manage_allocation.html', allocations=rows)

@app.route('/admin/edit_allocation/<int:alloc_id>', methods=['GET', 'POST'])
def edit_allocation(alloc_id):
    conn = get_db_connection()
    allocation = conn.execute('''
        SELECT aa.*, a.ItemName, a.Model, e.first_name, e.last_name
        FROM TblAllocateAssets aa
        JOIN TblAssets a ON aa.AssetId = a.AssetId
        JOIN tbl_employee e ON aa.EmployeeId = e.emp_id
        WHERE aa.AllocatedId = ?
    ''', (alloc_id,)).fetchone()

    if request.method == 'POST':
        conn.execute("UPDATE TblAllocateAssets SET Status = 'Returned' WHERE AllocatedId = ?", (alloc_id,))
        conn.execute("UPDATE TblAssets SET Status = 'Available' WHERE AssetId = ?", (allocation['AssetId'],))
        conn.commit()
        conn.close()
        flash("Asset returned", "success")
        return redirect(url_for('manage_allocation'))

    return render_template('edit_allocation.html', allocation=allocation)

@app.route('/admin/asset_history', methods=['GET'])
def asset_history():
    selected_emp_id = request.args.get('employee_id', type=int)
    conn = get_db_connection()
    employees = conn.execute("SELECT emp_id, first_name, last_name FROM tbl_employee WHERE Status = 'active'").fetchall()
    history = []
    if selected_emp_id:
        history = conn.execute('''
            SELECT aa.*, a.ItemName, a.Model FROM TblAllocateAssets aa
            JOIN TblAssets a ON aa.AssetId = a.AssetId
            WHERE aa.EmployeeId = ?
            ORDER BY aa.AllocateDate DESC
        ''', (selected_emp_id,)).fetchall()
    return render_template('asset_history.html', employees=employees, history=history, selected_emp_id=selected_emp_id)

@app.route('/employee/assets')
def employee_assets():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))

    conn = get_db_connection()
    assets = conn.execute('''
        SELECT aa.*, a.ItemName, a.Model
        FROM TblAllocateAssets aa
        JOIN TblAssets a ON aa.AssetId = a.AssetId
        WHERE aa.EmployeeId = ? AND aa.Status = 'Allocated'
        ORDER BY aa.AllocateDate DESC
    ''', (session['user_id'],)).fetchall()

    issues = conn.execute('''
        SELECT * FROM TblAssetIssues
        WHERE EmployeeId = ?
        ORDER BY ReportedDate DESC
    ''', (session['user_id'],)).fetchall()

    # Group issues by asset ID and status
    open_issues_by_asset = {}
    resolved_issues_by_asset = {}

    for i in issues:
        if i['Status'] == 'Resolved':
            resolved_issues_by_asset.setdefault(i['AssetId'], []).append(i)
        else:
            open_issues_by_asset.setdefault(i['AssetId'], []).append(i)

    return render_template('employee_assets.html',
                           assets=assets,
                           open_issues_by_asset=open_issues_by_asset,
                           resolved_issues_by_asset=resolved_issues_by_asset)

@app.route('/employee/report_issue/<int:asset_id>', methods=['POST'])
def report_asset_issue(asset_id):
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))

    issue_text = request.form['issue_text'].strip()
    if issue_text:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO TblAssetIssues (AssetId, EmployeeId, IssueText)
            VALUES (?, ?, ?)
        ''', (asset_id, session['user_id'], issue_text))
        conn.commit()
        conn.close()
        flash('Issue reported successfully', 'success')
    else:
        flash('Issue text cannot be empty.', 'error')
    
    return redirect(url_for('employee_assets'))

@app.route('/admin/resolve_issue/<int:issue_id>', methods=['POST'])
def resolve_issue(issue_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    comment = request.form.get('resolved_comment', '').strip()

    if not comment:
        flash('Resolution comment is required.', 'error')
        return redirect(url_for('manage_allocation'))

    conn = get_db_connection()
    conn.execute('''
        UPDATE TblAssetIssues
        SET Status = 'Resolved',
            ResolvedComment = ?,
            ResolvedDate = DATE('now')
        WHERE IssueId = ?
    ''', (comment, issue_id))
    conn.commit()
    conn.close()

    flash('Issue marked as resolved.', 'success')
    return redirect(url_for('manage_allocation'))

@app.route('/api/task_detail/<int:detail_id>')
def api_get_task_detail(detail_id):
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return jsonify({'error': 'Unauthorized'}), 401

    detail = db.get_task_detail(detail_id)
    if not detail or not db.verify_task_detail_owner(detail_id, session['user_id']):
        return jsonify({'error': 'Not found'}), 404

    task = db.get_task(detail[1])
    return jsonify({
        'detail_id': detail[0],
        'task_id': detail[1],
        'desc': detail[2],
        'status': detail[4],
        'task_name': task[1] if task else ''
    })

@app.route('/admin/quick_delete', methods=['GET'])
def admin_quick_delete():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    category = request.args.get('category')
    data = []

    if category == 'employee':
        data = db.get_employees()
    elif category == 'task':
        data, _ = db.get_all_tasks_with_details_paginated(1, 9999)
    elif category == 'leave_type':
        data = db.get_leave_types()
    elif category == 'expense_type':
        data = db.get_expense_types()
    

    return render_template('admin_quick_delete.html', category=category, data=data)

@app.route('/admin/delete_all/<category>', methods=['POST'])
def delete_all_category(category):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    try:
        if category == 'employee':
            db.delete_all_employees()
        elif category == 'task':
            db.delete_all_tasks()
        elif category == 'leave_type':
            db.delete_all_leave_types()
        elif category == 'expense_type':
            db.delete_all_expense_types()
        flash(f'All {category.replace("_", " ")}s deleted.', 'success')
    except Exception as e:
        flash(str(e), 'error')

    return redirect(url_for('admin_quick_delete', category=category))

@app.route('/admin/wiki_categories', methods=['GET', 'POST'])
def admin_wiki_categories():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        category = request.form['category'].strip()
        img_file = request.files.get('cat_img')
        img_filename = None
        if img_file and img_file.filename:
            filename = secure_filename(img_file.filename)
            img_file.save(os.path.join(app.config['WIKI_CAT_FOLDER'], filename))
            img_filename = filename
        db.add_wiki_category(category, img_filename)
        flash(f'Wiki category "{category}" added.', 'success')
        return redirect(url_for('admin_wiki_categories', msg=f'"{category}" saved'))
    cats = db.get_wiki_categories()
    msg = request.args.get('msg')
    return render_template('admin_wiki_category.html', cats=cats, msg=msg)

@app.route('/admin/edit_wiki_category/<int:cat_id>', methods=['POST'])
def edit_wiki_category(cat_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    new_cat = request.form['new_category'].strip()
    img_file = request.files.get('new_cat_img')
    img_filename = None
    if img_file and img_file.filename:
        filename = secure_filename(img_file.filename)
        img_file.save(os.path.join(app.config['WIKI_CAT_FOLDER'], filename))
        img_filename = filename
    db.update_wiki_category(cat_id, new_cat, img_filename)
    flash(f'Category updated to "{new_cat}"', 'success')
    return redirect(url_for('admin_wiki_categories'))

@app.route('/admin/delete_wiki_category/<int:cat_id>')
def delete_wiki_category(cat_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    db.delete_wiki_category(cat_id)
    flash('Wiki category deleted', 'success')
    return redirect(url_for('admin_wiki_categories'))

@app.route('/admin/add_wiki', methods=['GET', 'POST'])
def add_wiki():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        category_id = request.form['category_id']
        title       = request.form['title'].strip()
        descr       = request.form['descr']
        db.add_wiki_page(category_id, title, descr)
        flash(f'Wiki "{title}" added.', 'success')
        return redirect(url_for('view_wikis'))
    categories = db.get_wiki_categories()
    return render_template('add_wiki.html', categories=categories)

@app.route('/admin/view_wikis')
def view_wikis():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    wikis = db.get_wiki_pages()
    return render_template('view_wikis.html', wikis=wikis)

@app.route('/admin/edit_wiki/<int:wiki_id>', methods=['GET', 'POST'])
def edit_wiki(wiki_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    page = db.get_wiki_page(wiki_id)
    if not page:
        flash('Wiki not found.', 'error')
        return redirect(url_for('view_wikis'))
    if request.method == 'POST':
        category_id = request.form['category_id']
        title       = request.form['title'].strip()
        descr       = request.form['descr']
        db.update_wiki_page(wiki_id, category_id, title, descr)
        flash(f'Wiki "{title}" updated.', 'success')
        return redirect(url_for('view_wikis'))
    categories = db.get_wiki_categories()
    return render_template('edit_wiki.html', page=page, categories=categories)

@app.route('/admin/delete_wiki/<int:wiki_id>')
def delete_wiki(wiki_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    db.soft_delete_wiki_page(wiki_id)
    flash('Wiki deleted', 'success')
    return redirect(url_for('view_wikis'))

@app.route('/employee/wiki')
def employee_wiki_list():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    wikis = db.get_wiki_pages()
    return render_template('wiki_list.html', wikis=wikis)

@app.route('/employee/wiki/<int:wiki_id>')
def wiki_detail(wiki_id):
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    page = db.get_wiki_page(wiki_id)
    if not page:
        flash('Wiki not found.', 'error')
        return redirect(url_for('employee_wiki_list'))
    # record the view
    db.add_wiki_view(wiki_id, session['user_id'])
    return render_template('wiki_detail.html', page=page)

@app.route('/admin/wiki_views')
def admin_wiki_views():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))

    # read filter params
    start = request.args.get('start_date', default=None)
    end   = request.args.get('end_date',   default=None)
    wiki  = request.args.get('wiki_id',    type=int)

    # fetch data
    counts = db.get_wiki_view_counts(start, end)
    views  = db.get_wiki_views_filtered(start, end, wiki)
    pages  = db.get_wiki_pages()  # for the filter dropdown

    return render_template(
        'view_wiki_views.html',
        counts=counts,
        views=views,
        pages=pages,
        filter_start=start,
        filter_end=end,
        filter_wiki=wiki
    )

@app.route('/admin/add_policy', methods=['GET', 'POST'])
def add_policy():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        policy_name = request.form.get('policy_name', '').strip()
        file = request.files.get('policy_file')
        
        # Validation
        if not policy_name:
            flash('Policy name is required', 'error')
            return redirect(request.url)
        
        if not file or file.filename == '':
            flash('Please select a file', 'error')
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash('Only PDF files are allowed', 'error')
            return redirect(request.url)
        
        if db.policy_exists(policy_name):
            flash('Policy name already exists', 'error')
            return redirect(request.url)
        
        try:
            # Generate unique filename
            original_filename = secure_filename(file.filename)
            unique_filename = generate_unique_filename(original_filename)
            filepath = os.path.join(POLICIES_FOLDER, unique_filename)
            
            # Save file
            file.save(filepath)
            file_size = os.path.getsize(filepath)
            
            # Save to database
            db.add_policy_to_db(policy_name, filepath, unique_filename, original_filename, file_size)
            
            flash('Policy uploaded successfully!', 'success')
            return redirect(url_for('list_policies'))
            
        except Exception as e:
            flash(f'Error uploading policy: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('add_policy.html')

@app.route('/admin/list_policies')
def list_policies():
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    policies = db.get_all_policies()
    return render_template('list_policy.html', policies=policies)

@app.route('/admin/policy/<int:policy_id>')
def view_policy(policy_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    policy = db.get_policy_by_id(policy_id)
    if not policy:
        flash('Policy not found', 'error')
        return redirect(url_for('list_policies'))
    
    filepath = policy['FilePath']
    original_name = policy['OriginalFileName']
    
    if os.path.exists(filepath):
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        return send_from_directory(directory, filename, as_attachment=True, download_name=original_name)
    else:
        flash('Policy file not found', 'error')
        return redirect(url_for('list_policies'))

@app.route('/admin/delete_policy/<int:policy_id>', methods=['POST'])
def delete_policy(policy_id):
    if 'user_id' not in session or session['emp_type'] != 'admin':
        return redirect(url_for('login'))
    
    policy = db.get_policy_by_id(policy_id)
    if policy:
        try:
            # Delete file from filesystem
            if os.path.exists(policy['FilePath']):
                os.remove(policy['FilePath'])
            
            # Delete from database
            db.delete_policy(policy_id)
            flash('Policy deleted successfully', 'success')
            
        except Exception as e:
            flash(f'Error deleting policy: {str(e)}', 'error')
    else:
        flash('Policy not found', 'error')
    
    return redirect(url_for('list_policies'))

# Employee policy viewing
@app.route('/employee/policies')
def employee_policies():
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    
    policies = db.get_all_policies()
    return render_template('employee_policies.html', policies=policies)

@app.route('/employee/policy/<int:policy_id>')
def employee_view_policy(policy_id):
    if 'user_id' not in session or session['emp_type'] != 'emp':
        return redirect(url_for('login'))
    
    policy = db.get_policy_by_id(policy_id)
    if not policy:
        flash('Policy not found', 'error')
        return redirect(url_for('employee_policies'))
    
    filepath = policy['FilePath']
    original_name = policy['OriginalFileName']
    
    if os.path.exists(filepath):
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        return send_from_directory(directory, filename, as_attachment=True, download_name=original_name)
    else:
        flash('Policy file not found', 'error')
        return redirect(url_for('employee_policies'))

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error with traceback
    logging.exception("An unexpected error occurred")

    # Show an HTML error page (templates/error.html)
    return render_template("error.html", error=e), 500


if __name__ == '__main__':
    app.run(debug=True)