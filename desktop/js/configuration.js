$('#bt_deleteConfig').on('click', function () {
    bootbox.confirm('{{Etes-vous sûr de vouloir supprimer les configurations connues des robots?<br/>Vous devrez refaire le processus de découverte ensuite.}}', function (result) {
        if (result) {
            $.ajax({
                type: "POST",
                url: "plugins/dreame/core/ajax/dreame.ajax.php",
                data: {
                    action: "delete_config"
                },
                dataType: 'json',
                global: false,
                error: function (request, status, error) {
                    handleAjaxError(request, status, error);
                },
                success: function (data) {
                    if (data.state != 'ok') {
                        $('#div_alert').showAlert({ message: data.result, level: 'danger' });
                        return;
                    }
                    if (!isset(data.result)) {
                        $('#div_alert').showAlert({ message: 'Résultat vide', level: 'danger' });
                        return;
                    }
                    $('#div_alert').showAlert({ message: '{{Opération réalisée avec succès}}', level: 'success' });
                }
            });
        }
    });
});