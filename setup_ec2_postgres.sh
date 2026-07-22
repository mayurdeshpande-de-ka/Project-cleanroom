#!/bin/bash
# Run this script on your EC2 instance (Amazon Linux 2023 or similar)

echo "Installing PostgreSQL server..."
sudo dnf install -y postgresql15 postgresql15-server || sudo amazon-linux-extras install -y postgresql14

echo "Initializing database..."
sudo postgresql-setup --initdb || sudo postgresql-setup initdb

echo "Starting and enabling PostgreSQL service..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

echo "Creating database and user..."
sudo -u postgres psql -c "CREATE DATABASE local_backlog_db;"
sudo -u postgres psql -c "CREATE USER backlog_user WITH ENCRYPTED PASSWORD 'backlog_local_pass';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE local_backlog_db TO backlog_user;"
sudo -u postgres psql -d local_backlog_db -c "GRANT ALL ON SCHEMA public TO backlog_user;"

echo "Updating pg_hba.conf to allow password authentication locally..."
PG_HBA=$(sudo find /var/lib/pgsql -name pg_hba.conf)
sudo sed -i "s/ident/md5/g" $PG_HBA
sudo sed -i "s/peer/md5/g" $PG_HBA
sudo systemctl restart postgresql

echo "PostgreSQL installed and running locally!"
