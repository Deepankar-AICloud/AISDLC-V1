using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace SmartServe.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddFirstReviewAtToRetentionDisposalRecord : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<DateTimeOffset>(
                name: "FirstReviewAt",
                table: "RetentionDisposalRecords",
                type: "datetimeoffset",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "FirstReviewAt",
                table: "RetentionDisposalRecords");
        }
    }
}
