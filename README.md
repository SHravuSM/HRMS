# Project Tracking System

A comprehensive web-based project tracking system built with Flask, SQLite, HTML, Tailwind CSS, and JavaScript. This application allows administrators to manage employees, projects, and tasks while providing employees with a dashboard to track and update their assigned tasks.

## Features

### Admin Features
- **Employee Management**: Add new employees with complete profile information
- **Project Management**: Create and manage projects with priorities and deadlines
- **Task Management**: Assign tasks to employees with detailed descriptions and priorities
- **Dashboard**: View all task updates with filtering options by project, employee, and status
- **Task Details**: View detailed task progress and employee updates

### Employee Features
- **Personal Dashboard**: View assigned tasks for the current period
- **Task Updates**: Add daily work progress and status updates
- **Task Status Tracking**: Mark tasks as complete or incomplete

## Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: HTML5, Tailwind CSS, JavaScript
- **Icons**: Font Awesome
- **Authentication**: Session-based authentication with password hashing

## Database Schema

### Tables
1. **tbl_employee**: Employee information and authentication
2. **tbl_project**: Project details and status
3. **tbl_task**: Task assignments and tracking
4. **tbl_task_details**: Daily task updates from employees

## Installation

1. **Clone or download the project files**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the application**:
   Open your web browser and navigate to `http://localhost:5000`

## Default Login Credentials

### Admin Account
- **Email**: admin@company.com
- **Password**: admin123

## Usage

### For Administrators

1. **Login** with admin credentials
2. **Add Employees**: Navigate to "Add Employee" to create new user accounts
3. **Create Projects**: Use "Add Project" to set up new projects
4. **Assign Tasks**: Use "Add Task" to assign work to employees
5. **Monitor Progress**: Use the dashboard to track all task updates and progress

### For Employees

1. **Login** with employee credentials (created by admin)
2. **View Tasks**: See all assigned tasks on the dashboard
3. **Add Updates**: Click "Add Update" on any task to log daily progress
4. **Track Status**: Mark tasks as complete or incomplete

## Features Overview

### Security
- Password hashing using SHA-256
- Session-based authentication
- Role-based access control (Admin/Employee)
- Active/Inactive employee status management

### User Interface
- Modern, responsive design using Tailwind CSS
- Clean and intuitive navigation
- Real-time filtering and search capabilities
- Modal dialogs for detailed views
- Mobile-friendly responsive layout

### Data Management
- Automatic ID generation for all entities
- Foreign key relationships for data integrity
- Timestamp tracking for all records
- Flexible status management

## File Structure

```
Project Tracking/
├── app.py                 # Main Flask application
├── database.py            # Database operations and schema
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/            # HTML templates
│   ├── base.html         # Base template with navigation
│   ├── login.html        # Login page
│   ├── admin_dashboard.html    # Admin dashboard
│   ├── employee_dashboard.html # Employee dashboard
│   ├── add_employee.html # Add employee form
│   ├── add_project.html  # Add project form
│   └── add_task.html     # Add task form
└── static/               # Static files (currently empty)
```

## Customization

### Adding New Features
- Extend the database schema in `database.py`
- Add new routes in `app.py`
- Create corresponding HTML templates
- Update navigation in `base.html`

### Styling
- Modify Tailwind CSS classes in templates
- Add custom CSS in the static folder
- Update color scheme in the Tailwind config

## Production Deployment

Before deploying to production:

1. Change the secret key in `app.py`
2. Use a production WSGI server (e.g., Gunicorn)
3. Configure proper database backup procedures
4. Set up SSL/HTTPS
5. Configure environment variables for sensitive data

## Support

This is a complete, functional project tracking system ready for immediate use or further customization based on specific organizational needs.