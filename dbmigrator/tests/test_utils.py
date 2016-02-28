# -*- coding: utf-8 -*-
# ###
# Copyright (c) 2016, Rice University
# This software is subject to the provisions of the GNU Affero General
# Public License version 3 (AGPLv3).
# See LICENCE.txt for details.
# ###

import os.path
import unittest

import psycopg2

from . import testing


class UtilsTestCase(unittest.TestCase):
    def tearDown(self):
        with psycopg2.connect(testing.db_connection_string) as db_conn:
            with db_conn.cursor() as cursor:
                cursor.execute('DROP TABLE IF EXISTS a_table')

    def test_get_settings_from_entry_points(self):
        from ..utils import get_settings_from_entry_points

        testing.install_test_packages()

        contexts = testing.test_packages
        settings = {
            'db_connection_string': testing.db_connection_string,
            }

        get_settings_from_entry_points(settings, contexts)

        self.assertEqual(
            settings,
            {'migrations_directory': testing.test_migrations_directories,
             'db_connection_string': testing.db_connection_string,
             })

    def test_get_settings_from_config(self):
        from ..utils import get_settings_from_config

        settings = {
            'migrations_directory': '/tmp/',
            }

        get_settings_from_config(
            testing.test_config_path,
            ['db-connection-string', 'migrations-directory', 'does-not-exist'],
            settings)

        self.assertEqual(
            settings,
            {'db_connection_string':
                'dbname=people user=test host=db.example.org',
             'migrations_directory': '/tmp/'})

    def test_with_cursor(self):
        from ..utils import with_cursor

        self.called = False

        @with_cursor
        def func(cursor, arg_1, kwarg_1='kwarg_1', kwarg_2='kwarg_2',
                 db_connection_string=None):
            self.assertTrue(isinstance(cursor, psycopg2.extensions.cursor))
            self.assertEqual(arg_1, 'arg_1')
            self.assertEqual(kwarg_1, 'called')
            self.assertEqual(kwarg_2, 'kwarg_2')
            self.assertEqual(
                db_connection_string, testing.db_connection_string)
            self.called = True

        func('arg_1', kwarg_1='called',
             db_connection_string=testing.db_connection_string)
        self.assertTrue(self.called)

        with self.assertRaises(Exception) as cm:
            func('')

        self.assertEqual(str(cm.exception), 'db-connection-string missing')

    def test_import_migration(self):
        from ..utils import import_migration

        migration_path = os.path.join(
            testing.test_data_path, 'package-a', 'package_a', 'migrations',
            '20160228202637_add_table.py')

        migration = import_migration(migration_path)
        self.assertIn('up', dir(migration))
        self.assertIn('down', dir(migration))

        with psycopg2.connect(testing.db_connection_string) as db_conn:
            with db_conn.cursor() as cursor:
                try:
                    cursor.execute('SELECT * FROM a_table')
                    self.fail('a_table should not be in the database before '
                              'the migration is run')
                except psycopg2.ProgrammingError as e:
                    self.assertIn('relation "a_table" does not exist', str(e))

        with psycopg2.connect(testing.db_connection_string) as db_conn:
            with db_conn.cursor() as cursor:
                # Run the migration.
                migration.up(cursor)

                # Try accessing a_table created by the migration.
                cursor.execute('SELECT * FROM a_table')

                # Roll back the migration.
                migration.down(cursor)

        with psycopg2.connect(testing.db_connection_string) as db_conn:
            with db_conn.cursor() as cursor:
                try:
                    cursor.execute('SELECT * FROM a_table')
                    self.fail('a_table should not be in the database after '
                              'the migration is rolled back')
                except psycopg2.ProgrammingError as e:
                    self.assertIn('relation "a_table" does not exist', str(e))
