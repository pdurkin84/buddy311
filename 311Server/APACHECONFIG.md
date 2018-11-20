Listen 31102 https
<VirtualHost _default_:31102>
    WSGIDaemonProcess buddy311 threads=5
    WSGIScriptAlias / /var/www/html/311Server/adapter.wsgi
    SSLCertificateFile /etc/ssl/certs/www_buddy311_org.crt
    SSLCACertificateFile /etc/ssl/certs/www_buddy311_org.ca-bundle
    SSLCertificateKeyFile /etc/ssl/private/www.buddy311.org.key
    <Directory "/var/www/html/311Server">
        WSGIProcessGroup buddy311
        WSGIApplicationGroup %{GLOBAL}
        Order deny,allow
        Allow from all
    </Directory>
</VirtualHost>
