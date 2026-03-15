-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Tempo de geração: 13/03/2026 às 10:28
-- Versão do servidor: 10.4.32-MariaDB
-- Versão do PHP: 8.1.25

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Banco de dados: `abase`
--

-- --------------------------------------------------------

--
-- Estrutura para tabela `refinanciamento_itens`
--

CREATE TABLE `refinanciamento_itens` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `refinanciamento_id` bigint(20) UNSIGNED NOT NULL,
  `pagamento_mensalidade_id` bigint(20) UNSIGNED DEFAULT NULL,
  `tesouraria_pagamento_id` bigint(20) UNSIGNED DEFAULT NULL,
  `referencia_month` date NOT NULL,
  `status_code` varchar(2) DEFAULT NULL,
  `valor` decimal(12,2) DEFAULT NULL,
  `import_uuid` char(36) DEFAULT NULL,
  `source_file_path` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Despejando dados para a tabela `refinanciamento_itens`
--

INSERT INTO `refinanciamento_itens` (`id`, `refinanciamento_id`, `pagamento_mensalidade_id`, `tesouraria_pagamento_id`, `referencia_month`, `status_code`, `valor`, `import_uuid`, `source_file_path`, `created_at`, `updated_at`) VALUES
(1, 1, 176, NULL, '2025-10-01', '1', 350.00, NULL, NULL, '2025-12-23 11:23:28', '2025-12-23 11:23:28'),
(2, 1, 534, NULL, '2025-11-01', '2', 350.00, NULL, NULL, '2025-12-23 11:23:28', '2025-12-23 11:23:28'),
(3, 1, 614, NULL, '2025-12-01', '1', 350.00, NULL, NULL, '2025-12-23 11:23:28', '2025-12-23 11:23:28'),
(4, 2, 178, NULL, '2025-10-01', '1', 200.00, NULL, NULL, '2025-12-23 13:51:04', '2025-12-23 13:51:04'),
(5, 2, 536, NULL, '2025-11-01', '2', 200.00, NULL, NULL, '2025-12-23 13:51:04', '2025-12-23 13:51:04'),
(6, 2, 612, NULL, '2025-12-01', '1', 200.00, NULL, NULL, '2025-12-23 13:51:04', '2025-12-23 13:51:04'),
(7, 3, 202, NULL, '2025-10-01', '1', 150.00, NULL, NULL, '2025-12-24 14:52:38', '2025-12-24 14:52:38'),
(8, 3, 577, NULL, '2025-11-01', '2', 150.00, NULL, NULL, '2025-12-24 14:52:38', '2025-12-24 14:52:38'),
(9, 3, 619, NULL, '2025-12-01', '1', 150.00, NULL, NULL, '2025-12-24 14:52:38', '2025-12-24 14:52:38'),
(10, 4, 109, NULL, '2025-10-01', '1', 150.00, NULL, NULL, '2025-12-24 14:53:41', '2025-12-24 14:53:41'),
(11, 4, 428, NULL, '2025-11-01', '2', 150.00, NULL, NULL, '2025-12-24 14:53:41', '2025-12-24 14:53:41'),
(12, 4, 615, NULL, '2025-12-01', '1', 150.00, NULL, NULL, '2025-12-24 14:53:41', '2025-12-24 14:53:41'),
(13, 5, 15, NULL, '2025-10-01', '1', 500.00, NULL, NULL, '2025-12-24 14:54:03', '2025-12-24 14:54:03'),
(14, 5, 257, NULL, '2025-11-01', '2', 500.00, NULL, NULL, '2025-12-24 14:54:03', '2025-12-24 14:54:03'),
(15, 5, 621, NULL, '2025-12-01', '1', 500.00, NULL, NULL, '2025-12-24 14:54:03', '2025-12-24 14:54:03'),
(16, 6, 204, NULL, '2025-10-01', '1', 400.00, NULL, NULL, '2025-12-24 14:54:30', '2025-12-24 14:54:30'),
(17, 6, 579, NULL, '2025-11-01', '2', 400.00, NULL, NULL, '2025-12-24 14:54:30', '2025-12-24 14:54:30'),
(18, 6, 618, NULL, '2025-12-01', '1', 400.00, NULL, NULL, '2025-12-24 14:54:30', '2025-12-24 14:54:30'),
(19, 7, 41, NULL, '2025-10-01', '1', 150.00, NULL, NULL, '2025-12-24 14:55:16', '2025-12-24 14:55:16'),
(20, 7, 298, NULL, '2025-11-01', '2', 150.00, NULL, NULL, '2025-12-24 14:55:16', '2025-12-24 14:55:16'),
(21, 7, 622, NULL, '2025-12-01', '1', 150.00, NULL, NULL, '2025-12-24 14:55:16', '2025-12-24 14:55:16'),
(22, 8, 63, NULL, '2025-10-01', '1', 500.00, NULL, NULL, '2025-12-24 14:56:58', '2025-12-24 14:56:58'),
(23, 8, 330, NULL, '2025-11-01', '2', 500.00, NULL, NULL, '2025-12-24 14:56:58', '2025-12-24 14:56:58'),
(24, 8, 624, NULL, '2025-12-01', '1', 500.00, NULL, NULL, '2025-12-24 14:56:58', '2025-12-24 14:56:58'),
(25, 9, 35, NULL, '2025-10-01', '1', 100.00, NULL, NULL, '2025-12-24 14:57:57', '2025-12-24 14:57:57'),
(26, 9, 286, NULL, '2025-11-01', '2', 100.00, NULL, NULL, '2025-12-24 14:57:57', '2025-12-24 14:57:57'),
(27, 9, 623, NULL, '2025-12-01', '1', 100.00, NULL, NULL, '2025-12-24 14:57:57', '2025-12-24 14:57:57'),
(28, 10, 69, NULL, '2025-10-01', '1', 500.00, NULL, NULL, '2025-12-24 14:58:56', '2025-12-24 14:58:56'),
(29, 10, 339, NULL, '2025-11-01', '2', 500.00, NULL, NULL, '2025-12-24 14:58:56', '2025-12-24 14:58:56'),
(30, 10, 617, NULL, '2025-12-01', '1', 500.00, NULL, NULL, '2025-12-24 14:58:56', '2025-12-24 14:58:56'),
(31, 11, 165, NULL, '2025-10-01', '1', 133.00, NULL, NULL, '2025-12-26 15:54:32', '2025-12-26 15:54:32'),
(32, 11, 516, NULL, '2025-11-01', '2', 133.00, NULL, NULL, '2025-12-26 15:54:32', '2025-12-26 15:54:32'),
(33, 11, 611, NULL, '2025-12-01', '1', 133.00, NULL, NULL, '2025-12-26 15:54:32', '2025-12-26 15:54:32'),
(34, 12, 23, NULL, '2025-10-01', '1', 150.00, NULL, NULL, '2025-12-29 07:51:29', '2025-12-29 07:51:29'),
(35, 12, 270, NULL, '2025-11-01', '2', 150.00, NULL, NULL, '2025-12-29 07:51:29', '2025-12-29 07:51:29'),
(36, 12, 656, NULL, '2025-12-01', '1', 150.00, NULL, NULL, '2025-12-29 07:51:29', '2025-12-29 07:51:29'),
(37, 13, 210, NULL, '2025-10-01', '1', 150.00, NULL, NULL, '2025-12-29 07:54:44', '2025-12-29 07:54:44'),
(38, 13, 594, NULL, '2025-11-01', '2', 150.00, NULL, NULL, '2025-12-29 07:54:44', '2025-12-29 07:54:44'),
(39, 13, 1038, NULL, '2025-12-01', '1', 150.00, NULL, NULL, '2025-12-29 07:54:44', '2025-12-29 07:54:44'),
(40, 14, 14, NULL, '2025-10-01', '1', 275.46, NULL, NULL, '2025-12-29 07:55:06', '2025-12-29 07:55:06'),
(41, 14, 256, NULL, '2025-11-01', '2', 275.46, NULL, NULL, '2025-12-29 07:55:06', '2025-12-29 07:55:06'),
(42, 14, 620, NULL, '2025-12-01', '1', 275.46, NULL, NULL, '2025-12-29 07:55:06', '2025-12-29 07:55:06'),
(43, 15, 126, NULL, '2025-10-01', '1', 150.00, NULL, NULL, '2025-12-29 07:55:31', '2025-12-29 07:55:31'),
(44, 15, 455, NULL, '2025-11-01', '2', 150.00, NULL, NULL, '2025-12-29 07:55:31', '2025-12-29 07:55:31'),
(45, 15, 893, NULL, '2025-12-01', '1', 150.00, NULL, NULL, '2025-12-29 07:55:31', '2025-12-29 07:55:31'),
(46, 16, 112, NULL, '2025-10-01', '1', 500.00, NULL, NULL, '2025-12-30 09:30:36', '2025-12-30 09:30:36'),
(47, 16, 433, NULL, '2025-11-01', '2', 500.00, NULL, NULL, '2025-12-30 09:30:36', '2025-12-30 09:30:36'),
(48, 16, 613, NULL, '2025-12-01', '1', 500.00, NULL, NULL, '2025-12-30 09:30:36', '2025-12-30 09:30:36'),
(49, 17, 102, NULL, '2025-10-01', '1', 500.00, NULL, NULL, '2025-12-30 14:38:50', '2025-12-30 14:38:50'),
(50, 17, 409, NULL, '2025-11-01', '2', 500.00, NULL, NULL, '2025-12-30 14:38:50', '2025-12-30 14:38:50'),
(51, 17, 1070, NULL, '2025-12-01', '2', 500.00, NULL, NULL, '2025-12-30 14:38:50', '2025-12-30 14:38:50');

--
-- Índices para tabelas despejadas
--

--
-- Índices de tabela `refinanciamento_itens`
--
ALTER TABLE `refinanciamento_itens`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uniq_refi_item_month` (`refinanciamento_id`,`referencia_month`),
  ADD KEY `refinanciamento_itens_tesouraria_pagamento_id_foreign` (`tesouraria_pagamento_id`),
  ADD KEY `refi_item_origem_idx` (`pagamento_mensalidade_id`,`tesouraria_pagamento_id`),
  ADD KEY `refinanciamento_itens_referencia_month_index` (`referencia_month`),
  ADD KEY `refinanciamento_itens_import_uuid_index` (`import_uuid`);

--
-- AUTO_INCREMENT para tabelas despejadas
--

--
-- AUTO_INCREMENT de tabela `refinanciamento_itens`
--
ALTER TABLE `refinanciamento_itens`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=52;

--
-- Restrições para tabelas despejadas
--

--
-- Restrições para tabelas `refinanciamento_itens`
--
ALTER TABLE `refinanciamento_itens`
  ADD CONSTRAINT `refinanciamento_itens_pagamento_mensalidade_id_foreign` FOREIGN KEY (`pagamento_mensalidade_id`) REFERENCES `pagamentos_mensalidades` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `refinanciamento_itens_refinanciamento_id_foreign` FOREIGN KEY (`refinanciamento_id`) REFERENCES `refinanciamentos` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `refinanciamento_itens_tesouraria_pagamento_id_foreign` FOREIGN KEY (`tesouraria_pagamento_id`) REFERENCES `tesouraria_pagamentos` (`id`) ON DELETE SET NULL;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
