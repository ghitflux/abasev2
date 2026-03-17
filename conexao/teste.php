<?php

try {
    $pdo = require __DIR__ . '/pdo.php';
    $resultado = $pdo->query('SELECT DATABASE() AS banco, VERSION() AS versao')->fetch();

    echo 'Conexao OK' . PHP_EOL;
    echo 'Banco: ' . ($resultado['banco'] ?? 'desconhecido') . PHP_EOL;
    echo 'MySQL: ' . ($resultado['versao'] ?? 'desconhecido') . PHP_EOL;
} catch (Throwable $e) {
    http_response_code(500);

    echo 'Falha na conexao: ' . $e->getMessage() . PHP_EOL;
}
