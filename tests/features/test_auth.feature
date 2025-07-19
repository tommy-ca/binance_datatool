Feature: {{FEATURE_NAME}}
  As a user of the system
  I want to use test auth functionality
  So that I can achieve my business goals

Background:
  Given the system is running
  And the database is available
  And the authentication service is configured

  @authentication @happy-path
  Scenario: Successful user authentication
      Scenario: User logs in with valid credentials
      Given a user with email "user@example.com" and password "validPassword123"
      And the user account is active
      When the user submits the login form
      Then the system should authenticate the user
      And the system should return a valid JWT token
      And the token should expire in 15 minutes
      And the user should be redirected to the dashboard
      And the login event should be logged

  @authentication @error-handling
  Scenario: Failed authentication with invalid credentials
      Scenario: User attempts login with invalid credentials
      Given a user with email "user@example.com" and password "invalidPassword"
      When the user submits the login form
      Then the system should reject the authentication
      And the system should display "Invalid email or password"
      And the system should not return any token
      And the failed attempt should be logged
      And the user should remain on the login page

  @authentication @security
  Scenario: Account lockout after multiple failed attempts
      Scenario: Account gets locked after maximum failed attempts
      Given a user with email "user@example.com"
      And the user has already failed 2 login attempts
      When the user submits invalid credentials again
      Then the system should lock the account
      And the system should display "Account temporarily locked"
      And the system should prevent further login attempts for 15 minutes
      And the account lockout should be logged with timestamp

  @authentication @2fa @optional
  Scenario: Two-factor authentication flow
      Scenario: User completes 2FA authentication
      Given a user with email "user@example.com" and valid password
      And two-factor authentication is enabled for the user
      When the user submits valid credentials
      Then the system should send an SMS verification code
      And the system should display the 2FA verification form
      When the user enters the correct verification code
      Then the system should complete the authentication
      And the system should return a valid JWT token

