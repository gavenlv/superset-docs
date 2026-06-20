# language: en
# BDD Spec — RBAC (P3-A)

@rbac
Feature: Role-based access control
  As an administrator
  I need to manage users, roles and permissions

  Scenario: List all users
    When the client calls "/api/v1/users"
    Then the response contains the user list

  Scenario: User CRUD
    When the user creates a new user
    And modifies that user
    And deletes that user
    Then the full lifecycle completes without errors

  Scenario: List all roles
    When the client calls "/api/v1/roles"
    Then the response contains the role list

  Scenario: Role CRUD
    When the user creates a new role
    And modifies that role
    And deletes that role
    Then the full lifecycle completes without errors

  Scenario: Database permission matrix
    Given a low-privilege role exists
    When the user with that role accesses a specific database
    Then the behavior matches the permission setting

  Scenario: Chart permission
    Given a low-privilege role exists
    When the user with that role accesses a specific chart
    Then the behavior matches the permission setting

  Scenario: Non-admin login
    Given a non-admin user exists
    When that user logs in
    Then the user is redirected to the welcome page
