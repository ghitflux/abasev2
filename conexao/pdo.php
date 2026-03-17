<?php

$config = require __DIR__ . '/config.php';

$dsn = sprintf(
    '%s:host=%s;port=%d;dbname=%s;charset=%s',
    $config['DB_CONNECTION'],
    $config['DB_HOST'],
    $config['DB_PORT'],
    $config['DB_DATABASE'],
    $config['DB_CHARSET']
);

return new PDO(
    $dsn,
    $config['DB_USERNAME'],
    $config['DB_PASSWORD'],
    [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]
);
