# Nginx logs
sudo tail -f /var/log/nginx/error.log

# Gunicorn/Flask logs
sudo journalctl -u rsvp.service

# after git pull
sudo systemctl restart nanas-wedding-backend
sudo systemctl status nanas-wedding-backend

sudo nano /etc/systemd/system/nanas-wedding-backend.service