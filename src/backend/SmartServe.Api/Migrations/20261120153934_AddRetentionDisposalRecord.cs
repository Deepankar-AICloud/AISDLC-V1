using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace SmartServe.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddRetentionDisposalRecord : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "RetentionDisposalRecords",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    PortalRequestId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Kind = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    FinalStatus = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    SubmittedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    DisposedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_RetentionDisposalRecords", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_RetentionDisposalRecords_DisposedAt",
                table: "RetentionDisposalRecords",
                column: "DisposedAt");

            migrationBuilder.CreateIndex(
                name: "IX_RetentionDisposalRecords_PortalRequestId",
                table: "RetentionDisposalRecords",
                column: "PortalRequestId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "RetentionDisposalRecords");
        }
    }
}
