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

if (!isConnect('admin')) {
    throw new Exception('401 Unauthorized');
}
?>

<table class="table table-condensed tablesorter" id="table_healthdreame">
    <thead>
        <tr>
            <th>{{Nom}}</th>
            <th>{{MAC}}</th>
            <th>{{IP}}</th>
            <th>{{Status}}</th>
            <th>{{Bac plein}}</th>
            <th>{{Batterie}}</th>
        </tr>
    </thead>
    <tbody>
        <?php
        /** @var dreame */
        foreach (dreame::byType('dreame', true) as $eqLogic) {
            echo '<tr><td><a href="' . $eqLogic->getLinkToConfiguration() . '" style="text-decoration: none;">' . $eqLogic->getHumanName(true) . '</a></td>';
            echo '<td><span class="label label-info" style="font-size : 1em;">' . $eqLogic->getConfiguration(dreame::CFG_MAC) . '</span></td>';
            echo '<td><span class="label label-info" style="font-size : 1em;">' . $eqLogic->getConfiguration(dreame::CFG_IP_ADDR) . '</span></td>';
            echo '<td><span class="label label-info" style="font-size : 1em;">' . $eqLogic->getCmdInfoValue('state') . '</span></td>';
            echo '<td><span class="label label-info" style="font-size : 1em;">' . $eqLogic->getCmdInfoValue('bin_full') . '</span></td>';
            echo '<td><span class="label label-info" style="font-size : 1em;">' . $eqLogic->getCmdInfoValue('batPct') . '%</span></td>';
            echo '</tr>';
        }
        ?>
    </tbody>
</table>