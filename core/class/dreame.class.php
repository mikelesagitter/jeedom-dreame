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
require_once __DIR__ . '/../../../../core/php/core.inc.php';

require_once __DIR__ . '/../../vendor/autoload.php';

class dreame extends eqLogic {
    use MipsEqLogicTrait;

    const PYTHON_PATH = __DIR__ . '/../../resources/venv/bin/python3';

    const CFG_MODEL_FAMILY = 'model_family';
    const CFG_MAC = 'mac';
    const CFG_IP_ADDR = 'netinfo_addr';

    const MODEL_FAMILY_ROOMBA = 'Roomba';
    const MODEL_FAMILY_ROOMBA_CARPET_BOOST = 'RoombaCarpetBoost';
    const MODEL_FAMILY_BRAAVA = 'BraavaJet';

    private static $_MQTT2 = 'mqtt2';
    private static $_daemon_restart_needed = false;

    protected static function getSocketPort() {
        return config::byKey('socketport', __CLASS__, 55072);
    }

    public static function templateWidget() {
        $return = array('info' => array('string' => array()));
        $return['info']['string']['state'] = array(
            'template' => 'tmplmultistate',
            'replace' => array("#_desktop_width_#" => "80", "#_mobile_width_#" => "50"),
            'test' => array(
                array(
                    'operation' => "true",
                    'state_light' => "<img src='plugins/dreame/core/img/dreame_unknown.png' title ='" . __('Inconnu', __FILE__) . "'>",
                    'state_dark' => "<img src='plugins/dreame/core/img/dreame_unknown.png' title ='" . __('Inconnu', __FILE__) . "'>"
                ),
                array(
                    'operation' => "#value# == 'Charging' || #value# == 'Recharging'",
                    'state_light' => "<img src='plugins/dreame/core/img/dreame_charging.png' title ='" . __('En charge', __FILE__) . "'>",
                    'state_dark' => "<img src='plugins/dreame/core/img/dreame_charging.png' title ='" . __('En charge', __FILE__) . "'>"
                ),
                array(
                    'operation' => "#value# == 'Docking - End Mission' || #value# == 'Mission Completed'",
                    'state_light' => "<img src='plugins/dreame/core/img/dreame_completed.png' title ='" . __('Tâche achevée', __FILE__) . "'>",
                    'state_dark' => "<img src='plugins/dreame/core/img/dreame_completed.png' title ='" . __('Tâche achevée', __FILE__) . "'>"
                ),
                array(
                    'operation' => "#value# == 'Docking' || #value# == 'User Docking'",
                    'state_light' => "<img src='plugins/dreame/core/img/dreame_docking.png' title ='" . __('Retour à la base', __FILE__) . "'>",
                    'state_dark' => "<img src='plugins/dreame/core/img/dreame_docking.png' title ='" . __('Retour à la base', __FILE__) . "'>"
                ),
                array(
                    'operation' => "#value# == 'Paused'",
                    'state_light' => "<img src='plugins/dreame/core/img/dreame_paused.png' title ='" . __('Mis en pause', __FILE__) . "'>",
                    'state_dark' => "<img src='plugins/dreame/core/img/dreame_paused.png' title ='" . __('Mis en pause', __FILE__) . "'>"
                ),
                array(
                    'operation' => "#value# == 'Running'",
                    'state_light' => "<img src='plugins/dreame/core/img/dreame_running.png' title ='" . __('Nettoyage', __FILE__) . "'>",
                    'state_dark' => "<img src='plugins/dreame/core/img/dreame_running.png' title ='" . __('Nettoyage', __FILE__) . "'>"
                ),
                array(
                    'operation' => "#value# == 'Stopped'",
                    'state_light' => "<img src='plugins/dreame/core/img/dreame_stopped.png' title ='" . __('Arrêté', __FILE__) . "'>",
                    'state_dark' => "<img src='plugins/dreame/core/img/dreame_stopped.png' title ='" . __('Arrêté', __FILE__) . "'>"
                ),
                array(
                    'operation' => "#value# == 'Stuck' || #value# == 'Base Unplugged'",
                    'state_light' => "<img src='plugins/dreame/core/img/dreame_stuck.png' title ='" . __('Bloqué', __FILE__) . "'>",
                    'state_dark' => "<img src='plugins/dreame/core/img/dreame_stuck.png' title ='" . __('Bloqué', __FILE__) . "'>"
                ),
            )
        );
        $return['info']['numeric']['battery'] = array(
            'template' => 'tmplmultistate',
            'test' => array(
                array('operation' => "#value# >75", 'state_light' => '<i class="icon icon_green jeedom-batterie3"></i>', 'state_dark' => '<i class="icon icon_green jeedom-batterie3"></i>'),
                array('operation' => "#value# <= 75 && #value# > 50", 'state_light' => '<i class="icon icon_green jeedom-batterie2"></i>', 'state_dark' => '<i class="icon icon_green jeedom-batterie2"></i>'),
                array('operation' => "#value# <= 50 && #value# > 25", 'state_light' => '<i class="icon icon_yellow jeedom-batterie1"></i>', 'state_dark' => '<i class="icon icon_yellow jeedom-batterie1"></i>'),
                array('operation' => "#value# <= 25", 'state_light' => '<i class="icon icon_red jeedom-batterie0"></i>', 'state_dark' => '<i class="icon icon_red jeedom-batterie0"></i>')
            )
        );
        $return['info']['binary']['binfull'] = array(
            'template' => 'tmplicon',
            'replace' => array('#_icon_on_#' => '<i class=\'icon icon_red maison-poubelle\'></i>', '#_icon_off_#' => '<i class=\'icon icon_green fas fa-check\'></i>')
        );
        return $return;
    }

    private static function getTopicPrefix() {
        return 'iRobot';
    }

    public static function dependancy_install() {
        log::remove(__CLASS__ . '_update');
        return array('script' => __DIR__ . '/../../resources/install_#stype#.sh', 'log' => log::getPathToLog(__CLASS__ . '_update'));
    }

    public static function dependancy_info() {
        $return = array();
        $return['log'] = log::getPathToLog(__CLASS__ . '_update');
        $return['progress_file'] = jeedom::getTmpFolder(__CLASS__) . '/dependance';
        $return['state'] = 'ok';
        if (file_exists(jeedom::getTmpFolder(__CLASS__) . '/dependance')) {
            $return['state'] = 'in_progress';
        } elseif (!file_exists(self::PYTHON_PATH)) {
            $return['state'] = 'nok';
        } elseif (!self::pythonRequirementsInstalled(self::PYTHON_PATH, __DIR__ . '/../../resources/requirements.txt')) {
            $return['state'] = 'nok';
        }
        return $return;
    }

    public static function deamon_info() {
        $return = array();
        $return['log'] = __CLASS__;
        $return['launchable'] = 'ok';
        $return['state'] = 'nok';
        $pid_file = jeedom::getTmpFolder(__CLASS__) . '/daemon.pid';
        if (file_exists($pid_file)) {
            if (@posix_getsid(trim(file_get_contents($pid_file)))) {
                $return['state'] = 'ok';
            } else {
                shell_exec(system::getCmdSudo() . 'rm -rf ' . $pid_file . ' 2>&1 > /dev/null');
            }
        }
        if (!class_exists(self::$_MQTT2)) {
            $return['launchable'] = 'nok';
            $return['launchable_message'] = __('Le plugin mqtt2 n\'est pas installé', __FILE__);
        } else {
            if (self::$_MQTT2::deamon_info()['state'] != 'ok') {
                $return['launchable'] = 'nok';
                $return['launchable_message'] = __('Le démon mqtt2 n\'est pas demarré', __FILE__);
            }
        }
        return $return;
    }

    public static function removeMQTTTopicRegistration() {
        $topic = self::getTopicPrefix();
        log::add(__CLASS__, 'debug', "Stop listening to topic:'{$topic}'");
        self::$_MQTT2::removePluginTopic($topic);
    }

    public static function deamon_start() {
        $topic_prefix = self::getTopicPrefix();
        self::$_MQTT2::addPluginTopic(__CLASS__, $topic_prefix);
        log::add(__CLASS__, 'debug', "Listening to topic:'{$topic_prefix}'");
        self::deamon_stop();
        self::$_daemon_restart_needed = false;
        $deamon_info = self::deamon_info();
        if ($deamon_info['launchable'] != 'ok') {
            throw new Exception(__('Veuillez vérifier la configuration', __FILE__));
        }
        message::removeAll(__CLASS__, 'dreame_no_robot');

        $mqttInfos = self::$_MQTT2::getFormatedInfos();

        $excluded_blid = '';
        foreach (eqLogic::byType(__CLASS__) as $eqlogic) {
            if ($eqlogic->getIsEnable() == 0) {
                $excluded_blid .= $eqlogic->getLogicalId() . ',';
            }
        }

        $path = realpath(__DIR__ . '/../../resources/dreame');
        $cmd = self::PYTHON_PATH . " {$path}/dreamed.py";
        $cmd .= ' --loglevel ' . log::convertLogLevel(log::getLogLevel(__CLASS__));
        $cmd .= ' --host ' . $mqttInfos['ip'];
        $cmd .= ' --port ' . $mqttInfos['port'];
        $cmd .= ' --user "' . trim(str_replace('"', '\"', $mqttInfos['user'])) . '"';
        $cmd .= ' --password "' . trim(str_replace('"', '\"', $mqttInfos['password'])) . '"';
        $cmd .= ' --topic_prefix "' . trim(str_replace('"', '\"', $topic_prefix)) . '"';
        $cmd .= " --excluded_blid '{$excluded_blid}'";
        $cmd .= ' --socketport ' . self::getSocketPort();
        $cmd .= ' --callback ' . network::getNetworkAccess('internal', 'proto:127.0.0.1:port:comp') . '/plugins/dreame/core/php/jeedreame.php';
        $cmd .= ' --apikey ' . jeedom::getApiKey(__CLASS__);
        $cmd .= ' --pid ' . jeedom::getTmpFolder(__CLASS__) . '/daemon.pid';
        log::add(__CLASS__, 'info', 'Lancement démon');
        $result = exec($cmd . ' >> ' . log::getPathToLog(__CLASS__ . '_daemon') . ' 2>&1 &');
        $i = 0;
        while ($i < 10) {
            $deamon_info = self::deamon_info();
            if ($deamon_info['state'] == 'ok') {
                break;
            }
            sleep(1);
            $i++;
        }
        if ($i >= 10) {
            log::add(__CLASS__, 'error', __('Impossible de lancer le démon', __FILE__), 'unableStartDeamon');
            return false;
        }
        message::removeAll(__CLASS__, 'unableStartDeamon');
    }

    public static function deamon_stop() {
        $pid_file = jeedom::getTmpFolder(__CLASS__) . '/daemon.pid';
        if (file_exists($pid_file)) {
            $pid = intval(trim(file_get_contents($pid_file)));
            system::kill($pid);
        }
        sleep(1);
        system::kill('dreamed.py');
        // system::fuserk(config::byKey('socketport', __CLASS__));
        sleep(1);
    }

    public static function backupExclude() {
        return [
            'resources/venv'
        ];
    }

    public static function discoverRobots($login = '', $password = '', $address = '255.255.255.255') {
        $deamon_info = self::deamon_info();
        if ($deamon_info['state'] != 'ok') {
            throw new RuntimeException(__('Le démon n\'est pas démarré', __FILE__));
        }
        if ($address == '') $address = '255.255.255.255';
        if ($address == '255.255.255.255') {
            log::add(__CLASS__, 'info', __('Découverte des robots sur tout le réseau...', __FILE__));
        } else {
            log::add(__CLASS__, 'info', sprintf(__("Découverte du robot avec l'ip %s", __FILE__), $address));
        }
        self::sendToDaemon(array(
            'action' => 'discover',
            'login' => $login,
            'password' => $password,
            'address' => $address
        ));
    }

    /**
     *
     * @param string $blid
     * @param array $data
     * @return dreame
     */
    private static function getRobot($blid, $data) {
        $eqLogic = null;
        $name = $data['name'] ?? '';
        if (isset($data['detectedPad'])) {
            $robot_type = self::MODEL_FAMILY_BRAAVA;
            log::add(__CLASS__, 'debug', "Robot is {$robot_type}");
        } elseif (isset($data['carpetBoost']) && $data['carpetBoost'] == 1) {
            $robot_type = self::MODEL_FAMILY_ROOMBA_CARPET_BOOST;
            log::add(__CLASS__, 'debug', "Robot is {$robot_type}");
        } else {
            $robot_type = self::MODEL_FAMILY_ROOMBA;
        }

        if ($name != '') {
            /** @var dreame */
            $eqLogic = eqLogic::byLogicalId($name, __CLASS__);
        }

        if (is_object($eqLogic)) {
            log::add(__CLASS__, 'debug', "migrate from {$name} to blid:{$blid}");
            $eqLogic->setLogicalId($blid);
            $eqLogic->save(true);
        } else {
            /** @var dreame */
            $eqLogic = eqLogic::byLogicalId($blid, __CLASS__);
        }
        if (!is_object($eqLogic) && $name != '') {
            log::add(__CLASS__, 'info', "Creating new roomba with logicalId={$blid}");
            $eqLogic = new self();
            $eqLogic->setLogicalId($blid);
            $eqLogic->setEqType_name(__CLASS__);
            $eqLogic->setIsEnable(1);
            $eqLogic->setIsVisible(1);
            $eqLogic->setName($name);

            $eqLogic->save();

            event::add('dreame::newDevice');
        }
        if (is_object($eqLogic) && $eqLogic->getConfiguration(self::CFG_MODEL_FAMILY, self::MODEL_FAMILY_ROOMBA) == self::MODEL_FAMILY_ROOMBA && $robot_type != self::MODEL_FAMILY_ROOMBA) {
            $eqLogic->setConfiguration(self::CFG_MODEL_FAMILY, $robot_type);
            $eqLogic->save(true);
            $eqLogic->createCommands($robot_type);
        }
        return $eqLogic;
    }

    public static function handleMqttMessage($_message) {
        log::add(__CLASS__, 'debug', 'handle Mqtt Message:' . json_encode($_message));
        if (isset($_message[self::getTopicPrefix()]) && isset($_message[self::getTopicPrefix()]['feedback'])) {
            $feedback = $_message[self::getTopicPrefix()]['feedback'];
            foreach ($feedback as $robot => $data) {
                log::add(__CLASS__, 'debug', "Message for robot: {$robot}");
                $roomba = self::getRobot($robot, $data);
                if (!$roomba) {
                    log::add(__CLASS__, 'debug', 'no robot yet, waiting first payload');
                    return;
                }
                foreach ($data as $key => $value) {
                    switch ($key) {
                        case 'error_message':
                            $value = ($value == 'None') ? '' : $value;
                            if ($value != '' || $roomba->getCmdInfoValue('error_message') != '') {
                                $roomba->checkAndUpdateCmd('error_message', $value == 'None' ? '' : $value);
                            }
                            break;
                        case 'batInfo_mName':
                            if ($roomba->getConfiguration('battery_type', 'undefined') == 'undefined') {
                                $roomba->setConfiguration('battery_type', $value);
                                $roomba->save(true);
                            }
                            break;
                        case 'batPct':
                            $roomba->checkAndUpdateCmd('batPct', $value);
                            $roomba->batteryStatus($value);
                            break;
                        case 'bin_full':
                        case 'bin_present':
                        case 'childLock':
                            $roomba->checkAndUpdateCmd($key, $value === 'False' ? 0 : 1);
                            break;
                        case 'padWetness_disposable':
                        case 'padWetness_reusable':
                            $roomba->checkAndUpdateCmd('padWetness', $value);
                            break;
                        case 'netinfo_addr':
                        case 'netinfo_mask':
                        case 'netinfo_gw':
                        case 'netinfo_dns1':
                        case 'netinfo_dns2':
                            if (filter_var($value, FILTER_VALIDATE_IP) !== false) {
                                $roomba->setConfiguration($key, $value);
                                $roomba->save(true);
                            } elseif (filter_var($value, FILTER_VALIDATE_INT) !== false) {
                                $roomba->setConfiguration($key, long2ip($value));
                                $roomba->save(true);
                            } else {
                                log::add(__CLASS__, 'warning', "Unknown format: {$key}={$value}");
                            }
                            break;
                        case 'mac':
                        case 'hwPartsRev_wlan0HwAddr':
                            $roomba->setConfiguration(self::CFG_MAC, $value);
                            $roomba->save(true);
                            break;
                        case 'sku':
                            $roomba->setConfiguration($key, $value);
                            $roomba->save(true);
                            break;
                        case 'lastCommand_pmap_id':
                        case 'lastCommand_regions':
                        case 'lastCommand_user_pmapv_id':
                            if (isset($data['lastCommand_pmap_id'], $data['lastCommand_user_pmapv_id'], $data['lastCommand_regions'])) {
                                $roomba->create_start_regions_cmd($data['lastCommand_pmap_id'], $data['lastCommand_user_pmapv_id'], $data['lastCommand_regions']);
                            }
                            break;
                        case 'signal_rssi':
                        case 'signal_snr':
                        case 'signal_noise':
                            break;
                        default:
                            $cmd = $roomba->getCmd('info', $key);
                            if (!is_object($cmd)) {
                                // log::add(__CLASS__, 'debug', "ignoring sub-topic: {$key}=" . json_encode($value));
                            } else {
                                $roomba->checkAndUpdateCmd($cmd, $value);
                            }
                    }
                }
            }
        } else {
            log::add(__CLASS__, 'warning', 'Message is not for dreame');
            return;
        }
    }

    private function create_start_regions_cmd(string $pmap_id, string $user_pmapv_id, $regions) {
        if (empty($pmap_id) || empty($user_pmapv_id) || empty($regions) || !is_iterable($regions))
            return;

        foreach ($regions as $region) {
            log::add(__CLASS__, 'debug', "Detected region {$region}");
            $decoded_region = json_decode($region, true);

            if (!isset($decoded_region['type'], $decoded_region['region_id'])) {
                log::add(__CLASS__, 'debug', "no type or no id?");
                continue;
            }

            foreach ($this->getCmd('action', 'start_region', null, true) as $cmd) {
                if ($cmd->getConfiguration('pmap_id') == $pmap_id && $cmd->getConfiguration('region_id') == $decoded_region['region_id']) {
                    if ($cmd->getConfiguration('user_pmapv_id') != $user_pmapv_id) {
                        $cmd->setConfiguration('user_pmapv_id', $user_pmapv_id);
                        $cmd->save();
                        log::add(__CLASS__, 'info', __('Commande region mise à jour', __FILE__));
                    }
                    continue 2;
                }
            }

            $cmd = new dreameCmd();
            $cmd->setLogicalId('start_region');
            $cmd->setEqLogic_id($this->getId());
            $cmd->setName("start_{$pmap_id}_{$decoded_region['type']}_{$decoded_region['region_id']}");
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('pmap_id', $pmap_id);
            $cmd->setConfiguration('region_id', $decoded_region['region_id']);
            $cmd->setConfiguration('region_type', $decoded_region['type']);

            $cmd->save();
            log::add(__CLASS__, 'info', __('Nouvelle commande region créée', __FILE__));
        }
    }

    public function createCommands($commandType = '') {
        $cmds = self::getCommandsFileContent(__DIR__ . '/../config/commands.json');

        if ($commandType != '') {
            if (array_key_exists($commandType, $cmds)) {
                $this->createCommandsFromConfig($cmds[$commandType]);
            }
        } else {
            $this->createCommandsFromConfig($cmds['common']);
            $model_family = $this->getConfiguration(self::CFG_MODEL_FAMILY, self::MODEL_FAMILY_ROOMBA);
            if (array_key_exists($model_family, $cmds)) {
                $this->createCommandsFromConfig($cmds[$model_family]);
            }
        }
    }

    public function postInsert() {
        $this->createCommands();
    }

    public function preUpdate() {
        if ($this->getIsEnable() != eqLogic::byId($this->getId())->getIsEnable()) {
            log::add(__CLASS__, 'debug', "enable changed");
            self::$_daemon_restart_needed = true;
        }
    }

    public function postUpdate() {
        if (self::$_daemon_restart_needed) {
            log::add(__CLASS__, 'debug', "active eqLogic changed, restarting daemon");
            self::executeAsync('deamon_start');
        }
    }

    public function publish_message(string $type, string $payload) {
        self::$_MQTT2::publish(dreame::getTopicPrefix() . "/{$type}/" . $this->getLogicalId(), $payload);
    }
}

class dreameCmd extends cmd {
    public function formatValueWidget($value) {
        switch ($this->getLogicalId()) {
            case 'detectedPad':
                switch ($value) {
                    case 'reusableDry':
                        return 'Lingette réutilisable pour le balayage à sec';
                    case 'reusableWet':
                        return 'Lingette réutilisable pour le lavage des sols';
                    case 'dispDry':
                        return 'Lingette à usage unique pour le balayage à sec';
                    case 'dispWet':
                        return 'Lingette à usage unique pour le lavage des sols';
                    default:
                        return 'Invalide';
                }
                // case 'state':
                //     switch ($value) {
                //         case 'Charging':
                //         case 'Recharging':
                //             return 'En charge';
                //         default:
                //             return 'Inconnu';
                //     }
            default:
                return $value;
        }
    }

    public function execute($_options = null) {
        /** @var dreame */
        $eqLogic = $this->getEqLogic();

        switch ($this->getLogicalId()) {
            case 'set_rankOverlap':
                $payload = 'rankOverlap ' . $_options['select'];
                $eqLogic->publish_message('setting', $payload);
                break;
            case 'set_padWetness':
                $payload = 'padWetness {"disposable": %1$s, "reusable": %1$s}';
                $eqLogic->publish_message('setting', sprintf($payload, $_options['select']));
                break;
            case 'childLock_on':
                $eqLogic->publish_message('setting', 'childLock true');
                break;
            case 'childLock_off':
                $eqLogic->publish_message('setting', 'childLock false');
                break;
            case 'start_region':
                $payload = [
                    'command' => 'start',
                    'ordered' => 1,
                    'pmap_id' => $this->getConfiguration('pmap_id'),
                    'user_pmapv_id' => $this->getConfiguration('user_pmapv_id'),
                    'regions' => [[
                        'region_id' => $this->getConfiguration('region_id'),
                        'type' => $this->getConfiguration('region_type'),
                        // 'params' => [
                        //     'padWetness' => [
                        //         'disposable' => 1,
                        //         'reusable' => 1
                        //     ],
                        //     'rankOverlap' => 25
                        // ]
                    ]]
                ];
                $eqLogic->publish_message('command', json_encode($payload));
                break;
            default:
                $eqLogic->publish_message('command', $this->getLogicalId());
                break;
        };
    }
}
