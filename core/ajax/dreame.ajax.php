<?php

/* This file is part of Jeedom.
 *
 * Jeedom is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Jeedom is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Jeedom. If not, see <http://www.gnu.org/licenses/>.
 */

try {
  require_once __DIR__ . '/../../../../core/php/core.inc.php';
  include_file('core', 'authentification', 'php');

  if (!isConnect('admin')) {
    throw new Exception(__('401 - Accès non autorisé', __FILE__));
  }

  ajax::init();

  if (init('action') == 'discover') {
    dreame::discoverRobots(init('login'), init('password'), init('address'));
    ajax::success();
  } elseif (init('action') == 'delete_config') {
    $configFile = __DIR__ . '/../../data/config.ini';
    if (!file_exists($configFile)) {
      ajax::success('Le fichier n\'existe pas');
    } elseif (unlink($configFile)) {
      dreame::deamon_start();
      ajax::success();
    } else {
      ajax::error('Impossible de supprimer le fichier de configuration');
    }
  } elseif (init('action') == 'createCommands') {
    /**
     * @var dreame
     */
    $eqLogic = eqLogic::byId(init('id'));
    if (!is_object($eqLogic)) {
      throw new Exception(__('dreame eqLogic non trouvé : ', __FILE__) . init('id'));
    }

    try {
      $eqLogic->createCommands();
      ajax::success();
    } catch (\Throwable $th) {
      throw new Exception(__('Erreur lors de la création des commandes: ', __FILE__) . $th->getMessage());
    }
  }

  throw new Exception(__('Aucune methode correspondante à : ', __FILE__) . init('action'));
  /*     * *********Catch exeption*************** */
} catch (Exception $e) {
  ajax::error(displayException($e), $e->getCode());
}
