from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "for test"

    def handle(self, *args, **options):
        # TODO: Test Everything!
        self.stdout.write(self.style.SUCCESS('Successfully executed test_command!'))
        self.stdout.write('This is a simple message from your custom management command.')
        self.stdout.write(self.style.SUCCESS('Test command finished.'))