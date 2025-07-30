<?php

if (!isConnect('admin')) {
    throw new Exception('{{401 - Accès non autorisé}}');
}
$plugin = plugin::byId('dreame');
sendVarToJS('eqType', $plugin->getId());
$eqLogics = eqLogic::byType($plugin->getId());

?>

<div class="row row-overflow">
    <div class="col-xs-12 eqLogicThumbnailDisplay">
        <legend><i class="fas fa-cog"></i> {{Gestion}}</legend>
        <div class="eqLogicThumbnailContainer">
            <div class="cursor eqLogicAction logoSecondary" data-action="gotoPluginConf">
                <i class="fas fa-wrench"></i>
                <br>
                <span>{{Configuration}}</span>
            </div>
            <div class="cursor pluginAction logoSecondary" data-action="openLocation" data-location="<?= $plugin->getDocumentation() ?>">
                <i class="fas fa-book"></i>
                <br>
                <span>{{Documentation}}</span>
            </div>
            <div class="cursor pluginAction logoSecondary" data-action="openLocation" data-location="https://community.jeedom.com/tag/plugin-<?= $plugin->getId() ?>">
                <i class="fas fa-comments"></i>
                <br>
                <span>Community</span>
            </div>
            <div class="cursor logoSecondary" id="bt_syncdreame">
                <i class="fas fa-sync"></i>
                <br>
                <span>{{Découverte}}</span>
            </div>
            <div class="cursor logoSecondary" id="bt_healthdreame">
                <i class="fas fa-medkit"></i>
                <br>
                <span>{{Santé}}</span>
            </div>
        </div>
        <legend><i class="fas fa-robot"></i> {{Mes iRobots}}</legend>
        <div class="input-group" style="margin:5px;">
            <input class="form-control roundedLeft" placeholder="{{Rechercher}}" id="in_searchEqlogic" />
            <div class="input-group-btn">
                <a id="bt_resetSearch" class="btn" style="width:30px"><i class="fas fa-times"></i>
                </a><a class="btn roundedRight hidden" id="bt_pluginDisplayAsTable" data-coreSupport="1" data-state="0"><i class="fas fa-grip-lines"></i></a>
            </div>
        </div>
        <div class="eqLogicThumbnailContainer">
            <?php
            foreach ($eqLogics as $eqLogic) {
                $opacity = ($eqLogic->getIsEnable()) ? '' : 'disableCard';
                echo '<div class="eqLogicDisplayCard cursor ' . $opacity . '" data-eqLogic_id="' . $eqLogic->getId() . '">';
                echo '<img src="' . $eqLogic->getImage() . '">';
                echo "<br>";
                echo '<span class="name">' . $eqLogic->getHumanName(true, true) . '</span>';
                echo '<span class="hidden hiddenAsCard displayTableRight">';
                echo '<span class="label label-info">' . $eqLogic->getConfiguration(dreame::CFG_IP_ADDR) . '</span>';
                echo ($eqLogic->getIsVisible() == 1) ? '<i class="fas fa-eye" title="{{Equipement visible}}"></i>' : '<i class="fas fa-eye-slash" title="{{Equipement non visible}}"></i>';
                echo '</span>';
                echo '</div>';
            }
            ?>
        </div>
    </div>

    <div class="col-xs-12 eqLogic" style="display: none;">
        <div class="input-group pull-right" style="display:inline-flex">
            <span class="input-group-btn">
                <a class="btn btn-default btn-sm eqLogicAction roundedLeft" data-action="configure"><i class="fa fa-cogs"></i> {{Configuration avancée}}</a>
                <a class="btn btn-sm btn-success eqLogicAction" data-action="save"><i class="fas fa-check-circle"></i> {{Sauvegarder}}</a>
                <a class="btn btn-danger btn-sm eqLogicAction roundedRight" data-action="remove"><i class="fas fa-minus-circle"></i> {{Supprimer}}</a>
            </span>
        </div>
        <ul class="nav nav-tabs" role="tablist">
            <li role="presentation"><a href="#" class="eqLogicAction" aria-controls="home" role="tab" data-toggle="tab" data-action="returnToThumbnailDisplay"><i class="fas fa-arrow-circle-left"></i></a></li>
            <li role="presentation" class="active"><a href="#eqlogictab" aria-controls="home" role="tab" data-toggle="tab"><i class="fas fa-tachometer-alt"></i> {{Equipement}}</a></li>
            <li role="presentation"><a href="#commandtab" aria-controls="profile" role="tab" data-toggle="tab"><i class="fas fa-list"></i> {{Commandes}}</a></li>
        </ul>
        <div class="tab-content">
            <div role="tabpanel" class="tab-pane active" id="eqlogictab">
                <form class="form-horizontal">
                    <fieldset>
                        <div class="col-lg-8">
                            <legend><i class="fas fa-wrench"></i> {{Paramètres généraux}}</legend>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{Nom de l'équipement}}</label>
                                <div class="col-sm-4">
                                    <input type="text" class="eqLogicAttr form-control" data-l1key="id" style="display:none;">
                                    <input type="text" class="eqLogicAttr form-control" data-l1key="name" placeholder="{{Nom de l'équipement}}">
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{Objet parent}}</label>
                                <div class="col-sm-4">
                                    <select id="sel_object" class="eqLogicAttr form-control" data-l1key="object_id">
                                        <option value="">{{Aucun}}</option>
                                        <?php
                                        $options = '';
                                        foreach ((jeeObject::buildTree(null, false)) as $object) {
                                            $options .= '<option value="' . $object->getId() . '">' . str_repeat('&nbsp;&nbsp;', $object->getConfiguration('parentNumber')) . $object->getName() . '</option>';
                                        }
                                        echo $options;
                                        ?>
                                    </select>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{Catégorie}}</label>
                                <div class="col-sm-8">
                                    <?php
                                    foreach (jeedom::getConfiguration('eqLogic:category') as $key => $value) {
                                        echo '<label class="checkbox-inline">';
                                        echo '<input type="checkbox" class="eqLogicAttr" data-l1key="category" data-l2key="' . $key . '" >' . $value['name'];
                                        echo '</label>';
                                    }
                                    ?>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{Options}}</label>
                                <div class="col-sm-8">
                                    <label class="checkbox-inline"><input type="checkbox" class="eqLogicAttr" data-l1key="isEnable" checked>{{Activer}}</label>
                                    <label class="checkbox-inline"><input type="checkbox" class="eqLogicAttr" data-l1key="isVisible" checked>{{Visible}}</label>
                                </div>
                            </div>
                        </div>

                        <div class="col-lg-4">
                            <legend><i class="fas fa-info"></i> {{Informations}}</legend>

                            <div class="form-group">
                                <label class="col-sm-4 control-label"></label>
                                <div class="col-sm-8">
                                    <a id="bt_createCommands" class="btn btn-default"><i class="fas fa-search"></i> {{Créer les commandes manquantes}}</a>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{MAC}}</label>
                                <div class="col-sm-8">
                                    <span class="label label-default eqLogicAttr" data-l1key="configuration" data-l2key="mac"></span>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{IP}}</label>
                                <div class="col-sm-8">
                                    <span class="label label-default eqLogicAttr" data-l1key="configuration" data-l2key="netinfo_addr"></span>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{Masque}}</label>
                                <div class="col-sm-8">
                                    <span class="label label-default eqLogicAttr" data-l1key="configuration" data-l2key="netinfo_mask"></span>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{Passerelle}}</label>
                                <div class="col-sm-8">
                                    <span class="label label-default eqLogicAttr" data-l1key="configuration" data-l2key="netinfo_gw"></span>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{DNS 1}}</label>
                                <div class="col-sm-8">
                                    <span class="label label-default eqLogicAttr" data-l1key="configuration" data-l2key="netinfo_dns1"></span>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{DNS 2}}</label>
                                <div class="col-sm-8">
                                    <span class="label label-default eqLogicAttr" data-l1key="configuration" data-l2key="netinfo_dns2"></span>
                                </div>
                            </div>

                            <div class="form-group">
                                <label class="col-sm-4 control-label">{{Modèle}}</label>
                                <div class="col-sm-8">
                                    <span class="label label-default eqLogicAttr" data-l1key="configuration" data-l2key="sku"></span>
                                </div>
                            </div>
                        </div>
                    </fieldset>
                </form>
            </div>
            <div role="tabpanel" class="tab-pane" id="commandtab">
                <div class="table-responsive">
                    <table id="table_cmd" class="table table-bordered table-condensed">
                        <thead>
                            <tr>
                                <th style="min-width:220px;width:350px;">{{Nom}}</th>
                                <th style="min-width:140px;width:200px;">{{Type}}</th>
                                <th style="min-width:260px;">{{Options}}</th>
                                <th>{{Etat}}</th>
                                <th style="min-width:80px;width:140px;">{{Actions}}</th>
                            </tr>
                        </thead>
                        <tbody>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<div id="md_modal_dreame" title="{{Découverte des robots}}">
    <form class="form-horizontal" style="overflow:hidden !important;">
        <div class="form-group">
            <label class="col-sm-6 control-label">{{Méthode}}</label>
            <div class="col-sm-6">
                <select class="" id="irobot_method">
                    <option value="" disabled selected>{{Sélectionnez une méthode}}</option>
                    <option value="local">Connexion locale</option>
                    <option value="cloud">Connexion cloud</option>
                </select>
            </div>
        </div>
        <div class="irobot_local">
            <div class="alert alert-info globalRemark">
                <ul>
                    <li>Assurez-vous que les robots à découvrir sont sur la base de recharge et allumés (voyant vert allumé).</li>
                    <li>Ensuite, appuyez et maintenez le bouton HOME de votre robot jusqu'à ce qu'il émette une série de tonalités (environ 2 secondes).</li>
                    <li>Relâchez le bouton et le voyant WIFI devrait clignoter.</li>
                    <li>Cliquez sur le bouton <i>Continuer</i> ci-dessous.</li>
                </ul>
            </div>
        </div>
        <div class="irobot_cloud">
            <div class="alert alert-info globalRemark">
                Saisissez l'adresse eMail et le mot de passe de votre compte iRobot afin que le plugin se connecte au cloud pour récupérer la liste des robots configurés et leur mot de passe. <br>
                Ces informations ne sont pas sauvegardées et la connexion cloud ne sera pas utilisée pour contrôler le robot, elle est uniquement utilisée pour récupérer les informations nécessaires à la configuration.
            </div>
            <div class="form-group ">
                <label class="col-sm-6 control-label">{{Identifiant}}</label>
                <div class="col-sm-6">
                    <input type="text" class="form-control" id="irobot_login" placeholder="{{Adresse eMail iRobot}}" />
                </div>
            </div>
            <div class="form-group">
                <label class="col-sm-6 control-label">{{Mot de passe}}</label>
                <div class="col-sm-6">
                    <input type="password" class="form-control" id="irobot_password" placeholder="{{Mot de passe iRobot}}" />
                </div>
            </div>
        </div>
        <div class="form-group">
            <label class="col-sm-6 control-label">
                {{IP du robot (optionelle)}}
                <sup><i class="fas fa-question-circle" title="{{uniquement nécessaire si le robot n'est pas sur le même lan que Jeedom}}"></i></sup>
            </label>
            <div class="col-sm-6">
                <input type="text" class="form-control" id="irobot_ip" placeholder="255.255.255.255" />
            </div>
        </div>
    </form>
</div>

<?php include_file('desktop', 'dreame', 'js', 'dreame'); ?>
<?php include_file('core', 'plugin.template', 'js'); ?>