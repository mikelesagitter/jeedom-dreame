
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

$("#table_cmd").sortable({ axis: "y", cursor: "move", items: ".cmd", placeholder: "ui-state-highlight", tolerance: "intersect", forcePlaceholderSize: true });

function addCmdToTable(_cmd) {
  if (!isset(_cmd)) {
    var _cmd = { configuration: {} };
  }
  if (!isset(_cmd.configuration)) {
    _cmd.configuration = {};
  }
  let tr = '<tr class="cmd" data-cmd_id="' + init(_cmd.id) + '">';

  tr += '<td>';
  tr += '<span class="cmdAttr" data-l1key="id" style="display:none;"></span>';

  tr += '<div class="input-group">';
  tr += '<input class="cmdAttr form-control input-sm roundedLeft" data-l1key="name" placeholder="{{Nom de la commande}}">';
  tr += '<span class="input-group-btn"><a class="cmdAction btn btn-sm btn-default" data-l1key="chooseIcon" title="{{Choisir une icône}}"><i class="fas fa-icons"></i></a></span>';
  tr += '<span class="cmdAttr input-group-addon roundedRight" data-l1key="display" data-l2key="icon" style="font-size:19px;padding:0 5px 0 0!important;"></span>';
  tr += '</div>';
  tr += '<select class="cmdAttr form-control input-sm" data-l1key="value" disabled style="display:none;margin-top:5px;" title="{{Commande info liée}}">';
  tr += '<option value="">{{Aucune}}</option>';
  tr += '</select>';
  tr += '</td>';

  tr += '<td>';
  tr += '<span class="type" type="' + init(_cmd.type) + '">' + jeedom.cmd.availableType() + '</span>'
  tr += '<span class="subType" subType="' + init(_cmd.subType) + '"></span>'
  tr += '</td>';

  tr += '<td>';
  tr += '<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isVisible" checked/>{{Afficher}}</label> ';
  tr += '<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isHistorized" checked/>{{Historiser}}</label> ';
  tr += '<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="display" data-l2key="invertBinary"/>{{Inverser}}</label> ';
  tr += '<div style="margin-top:7px;">';
  tr += '<input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="minValue" placeholder="{{Min}}" title="{{Min}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">';
  tr += '<input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="maxValue" placeholder="{{Max}}" title="{{Max}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">';
  tr += '<input class="tooltips cmdAttr form-control input-sm" data-l1key="unite" placeholder="Unité" title="{{Unité}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">';
  tr += '</div>';
  tr += '</td>';

  tr += '<td>';
  tr += '<span class="cmdAttr" data-l1key="htmlstate"></span>';
  tr += '</td>';

  tr += '<td>';
  if (is_numeric(_cmd.id)) {
    tr += '<a class="btn btn-default btn-xs cmdAction" data-action="configure"><i class="fas fa-cogs"></i></a> ';
    tr += '<a class="btn btn-default btn-xs cmdAction" data-action="test"><i class="fas fa-rss"></i> {{Tester}}</a>';
  }
  tr += '<i class="fas fa-minus-circle pull-right cmdAction cursor" data-action="remove" title="{{Supprimer la commande}}"></i>';
  tr += '</td>';
  tr += '</tr>';

  $('#table_cmd tbody').append(tr);

  const $tr = $('#table_cmd tbody tr:last');
  jeedom.eqLogic.buildSelectCmd({
    id: $('.eqLogicAttr[data-l1key=id]').value(),
    filter: { type: 'info' },
    error: function (error) {
      $('#div_alert').showAlert({ message: error.message, level: 'danger' });
    },
    success: function (result) {
      $tr.find('.cmdAttr[data-l1key=value]').append(result);
      $tr.setValues(_cmd, '.cmdAttr');
      jeedom.cmd.changeType($tr, init(_cmd.subType));

      $tr.find('.cmdAttr[data-l1key=type],.cmdAttr[data-l1key=subType]').prop("disabled", true);
    }
  });
}

$('.pluginAction[data-action=openLocation]').on('click', function () {
  window.open($(this).attr("data-location"), "_blank", null);
});

$('#bt_healthdreame').on('click', function () {
  $('#md_modal').dialog({ title: "{{Santé iRobot}}" });
  $('#md_modal').load('index.php?v=d&plugin=dreame&modal=health').dialog('open');
});

$('body').off('dreame::newDevice').on('dreame::newDevice', function (_event, _options) {
  if (modifyWithoutSave) {
    $('#div_alert').showAlert({ message: '{{Un nouveau robot a été ajouté. Veuillez réactualiser la page}}', level: 'warning' });
  } else {
    $('#div_alert').showAlert({ message: '{{Un nouveau robot a été ajouté. Actualisation de la page dans 5s...}}', level: 'success' });
    setTimeout(function () {
      window.location.replace("index.php?v=d&m=dreame&p=dreame");
    }, 5000);
  }
});

$('#bt_createCommands').on('click', function () {
  $.ajax({
    type: "POST",
    url: "plugins/dreame/core/ajax/dreame.ajax.php",
    data: {
      action: "createCommands",
      id: $('.eqLogicAttr[data-l1key=id]').value()
    },
    dataType: 'json',
    error: function (request, status, error) {
      handleAjaxError(request, status, error);
    },
    success: function (data) {
      if (data.state != 'ok') {
        $('#div_alert').showAlert({ message: data.result, level: 'danger' });
        return;
      }
      $('#div_alert').showAlert({ message: '{{Opération réalisée avec succès}}', level: 'success' });
      $('.eqLogicDisplayCard[data-eqLogic_id=' + $('.eqLogicAttr[data-l1key=id]').value() + ']').click();
    }
  });
});

$('#md_modal_dreame').dialog({
  autoOpen: false,
  width: '600',
  closeText: '',
  buttons: {
    "{{Annuler}}": function () {
      $(this).dialog("close");
    },
    "{{Continuer}}": function () {
      $(this).dialog("close");
      $.ajax({
        type: "POST",
        url: "plugins/dreame/core/ajax/dreame.ajax.php",
        data: {
          action: "discover",
          login: $('#irobot_login').value(),
          password: $('#irobot_password').value(),
          address: $('#irobot_ip').value(),
        },
        dataType: 'json',
        error: function (request, status, error) {
          handleAjaxError(request, status, error);
        },
        success: function (data) {
          if (data.state != 'ok') {
            $('#div_alert').showAlert({ message: data.result, level: 'danger' });
            return;
          }
          // $('#password_input').value(data.result);
          $('#div_alert').showAlert({ message: '{{Découverte en cours, veuillez patienter.}}', level: 'success' });
        }
      });
    }
  }
});

$('#bt_syncdreame').on('click', function () {
  $("#irobot_method").val("");
  $('#irobot_login').val('');
  $('#irobot_password').val('');
  $('#irobot_ip').val('');
  $('.irobot_local').hide();
  $('.irobot_cloud').hide();
  $('#md_modal_dreame').dialog('open');
});

$("#irobot_method").change(function () {
  if ($(this).val() == 'local') {
    $('.irobot_local').show();
    $('.irobot_cloud').hide();
  } else {
    $('.irobot_local').hide();
    $('.irobot_cloud').show();
  }
});