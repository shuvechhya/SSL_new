# SSL_new

This project is a web application hosted on a Dockerized environment on a remote Linux server.  
It is configured with an automated CI/CD pipeline that deploys changes on push.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Deployment](#deployment)
  - [Manual Deployment](#manual-deployment)
  - [Automated CI/CD](#automated-cicd)
- [Server Setup](#server-setup)
- [CI/CD Runner](#cicd-runner)
- [Common Issues](#common-issues)
- [License](#license)
- [Pipeline Badge (Optional)](#pipeline-badge-optional)

---

## Project Structure
/home/shuvechhya/ssl/SSL_new
├── .gitlab-ci.yml          # CI/CD pipeline definition
├── docker-compose.yml      # Docker Compose file
├── (application files)

## Automated CI/CD
The .gitlab-ci.yml pipeline is configured to:

SSH into the server

Pull the latest changes

Restart Docker Compose

The pipeline runs automatically when code is pushed to the main branch.

Server Setup
The server must have the following:

Docker installed

Docker Compose installed

User shuvechhya added to the Docker group:
sudo usermod -aG docker shuvechhya

Git installed

CI/CD Runner
GitLab Runner is installed on the server.
