<?php
// The HTTP port is loopback-only; the dedicated Nginx host overwrites this header.
if (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https') {
    $_SERVER['HTTPS'] = 'on';
}
$config['product_name'] = 'Почта Визитки';
$config['language'] = 'ru_RU';
$config['des_key'] = getenv('ROUNDCUBE_DES_KEY');
$config['enable_installer'] = false;
$config['force_https'] = true;
$config['session_samesite'] = 'Lax';
$config['smtp_user'] = '%u';
$config['smtp_pass'] = '%p';
$config['enable_spellcheck'] = false;
$config['smtp_log'] = false;
